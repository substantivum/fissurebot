import discord
from discord.ext import commands
import asyncio

def setup(bot):
    intents = discord.Intents.default()
    intents.voice_states = True
    intents.members = True
    intents.message_content = True

    # ID стартового канала
    JOIN_CHANNEL_ID = 1374700290539917434  # ← замените на ваш

    # Хранилище: {voice_channel_id: (owner, text_channel)}
    private_rooms = {}

    @bot.event
    async def on_ready():
        print(f'rooms.py setup complete')

    class RoomControlView(discord.ui.View):
        def __init__(self, owner, voice_channel, text_channel):
            super().__init__(timeout=None)
            self.owner = owner
            self.voice_channel = voice_channel
            self.text_channel = text_channel

        async def interaction_check(self, interaction: discord.Interaction):
            if interaction.user != self.owner:
                await interaction.response.send_message("Вы не являетесь владельцем этой комнаты.", ephemeral=True)
                return False
            return True

        @discord.ui.button(label="➕ Пригласить", style=discord.ButtonStyle.green)
        async def invite_member(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Укажите участника для приглашения: `@пользователь`", ephemeral=True)

            try:
                msg = await bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel, timeout=30)
                member = msg.mentions[0]
                await self.voice_channel.set_permissions(member, connect=True)
                await self.text_channel.set_permissions(member, view_channel=True, send_messages=True)
                await interaction.followup.send(f"{member.mention} теперь может зайти и писать в комнату.")
            except asyncio.TimeoutError:
                await interaction.followup.send("Время ожидания истекло.", ephemeral=True)
            except IndexError:
                await interaction.followup.send("Не указан участник.", ephemeral=True)

        @discord.ui.button(label="➖ Выгнать", style=discord.ButtonStyle.red)
        async def kick_member(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Укажите участника для выгона: `@пользователь`", ephemeral=True)

            try:
                msg = await bot.wait_for('message', check=lambda m: m.author == interaction.user and m.channel == interaction.channel, timeout=30)
                member = msg.mentions[0]

                if member not in self.voice_channel.members:
                    await interaction.followup.send(f"{member.mention} не находится в комнате.", ephemeral=True)
                    return

                await self.voice_channel.set_permissions(member, overwrite=None)
                await self.text_channel.set_permissions(member, overwrite=None)

                join_channel = bot.get_channel(JOIN_CHANNEL_ID)
                if join_channel and isinstance(join_channel, discord.VoiceChannel):
                    await member.move_to(join_channel)

                await interaction.followup.send(f"{member.mention} был выгнан из комнаты.")

            except asyncio.TimeoutError:
                await interaction.followup.send("Время ожидания истекло.", ephemeral=True)
            except IndexError:
                await interaction.followup.send("Не указан участник.", ephemeral=True)

        @discord.ui.button(label="🔒 Закрыть комнату", style=discord.ButtonStyle.blurple)
        async def close_room(self, interaction: discord.Interaction, button: discord.ui.Button):
            everyone = self.voice_channel.guild.default_role

            # Убираем доступ у всех
            await self.voice_channel.set_permissions(everyone, connect=False)
            await self.text_channel.set_permissions(everyone, view_channel=False, send_messages=False)

            # Возвращаем права владельцу
            await self.voice_channel.set_permissions(self.owner, connect=True, manage_channels=True)
            await self.text_channel.set_permissions(self.owner, view_channel=True, send_messages=True, manage_channels=True)

            await interaction.response.send_message("Комната закрыта для всех, кроме вас.", ephemeral=True)

        @discord.ui.button(label="🔓 Открыть комнату", style=discord.ButtonStyle.gray)
        async def open_room(self, interaction: discord.Interaction, button: discord.ui.Button):
            everyone = self.voice_channel.guild.default_role

            # Восстанавливаем общие права
            await self.voice_channel.set_permissions(everyone, connect=True)
            await self.text_channel.set_permissions(everyone, view_channel=True, send_messages=True)

            # Владелец сохраняет полный доступ
            await self.voice_channel.set_permissions(self.owner, connect=True, manage_channels=True)
            await self.text_channel.set_permissions(self.owner, view_channel=True, send_messages=True, manage_channels=True)

            await interaction.response.send_message("Комната снова открыта для всех.", ephemeral=True)


    @bot.event
    async def on_voice_state_update(member, before, after):
        if after.channel and after.channel.id == JOIN_CHANNEL_ID:
            guild = member.guild

            try:
                category = after.channel.category

                # Создаём голосовой канал
                voice_channel = await guild.create_voice_channel(
                    name=f"Комната {member.display_name}",
                    category=category,
                    reason="Создана по запросу пользователя"
                )

                # Создаём текстовой канал
                text_channel = await guild.create_text_channel(
                    name=f"чат-{member.name.lower()}",
                    category=category,
                    reason="Текстовый канал для приватной комнаты"
                )

                # Убираем доступ у всех по умолчанию
                await text_channel.set_permissions(guild.default_role, view_channel=False, send_messages=False)

                # Сохраняем данные: владелец + текстовой канал
                private_rooms[voice_channel.id] = (member, text_channel)

                # Назначаем права владельцу
                await voice_channel.set_permissions(member, connect=True, manage_channels=True)
                await text_channel.set_permissions(member, view_channel=True, send_messages=True, manage_channels=True)

                # Перемещаем пользователя в новую комнату
                await member.move_to(voice_channel)

                # Отправляем сообщение с кнопками в текстовой канал
                embed = discord.Embed(
                    title="🎛 Управление комнатой",
                    description="Используйте кнопки ниже для управления вашей комнатой.",
                    color=discord.Color.blue()
                )
                view = RoomControlView(owner=member, voice_channel=voice_channel, text_channel=text_channel)
                await text_channel.send(embed=embed, view=view)

                # Функция удаления комнаты, если все покинут
                async def check_empty_room(vc, tc):
                    while True:
                        try:
                            await bot.wait_for('voice_state_update', timeout=30)
                            if len(vc.members) == 0:
                                try:
                                    await vc.delete(reason="Комната пустая")
                                except discord.NotFound:
                                    pass
                                try:
                                    await tc.delete(reason="Комната пустая")
                                except discord.NotFound:
                                    pass
                                if vc.id in private_rooms:
                                    del private_rooms[vc.id]
                                break
                        except asyncio.TimeoutError:
                            continue
                        except discord.NotFound:
                            if vc.id in private_rooms:
                                del private_rooms[vc.id]
                            break

                bot.loop.create_task(check_empty_room(voice_channel, text_channel))

            except Exception as e:
                print(f"[Ошибка создания комнаты] {e}")
