import os
import discord
from discord.ext import commands
from discord.ui import Button, View

# إعدادات الصلاحيات الأساسية للبوت
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# أيدي الروم الصوتي الرئيسي الذي يفتح الرومات المؤقتة
MAIN_VOICE_CHANNEL_ID = 1514653516017172490

# قاموس لحفظ الرومات المؤقتة وملاكها والشات الخاص بها
# التركيب: {voice_channel_id: {"owner_id": member_id, "text_channel_id": text_id}}
temp_rooms = {}

@bot.event
async def on_ready():
    print(f"=== تم تشغيل البot بنجاح بواسطة: {bot.user.name} ===")

# كلاس أزرار التحكم داخل شات الروم المؤقت
class RoomControlView(View):
    def __init__(self, voice_channel: discord.VoiceChannel, text_channel: discord.TextChannel, owner: discord.Member):
        super().__init__(timeout=None) # الأزرار لا تنتهي صلاحيتها
        self.voice_channel = voice_channel
        self.text_channel = text_channel
        self.owner = owner

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # التأكد أن الشخص الذي يضغط على الزر هو صاحب الروم فقط
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ عذراً، هذا الزر مخصص لصاحب الروم فقط!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔒 قفل الروم", style=discord.ButtonStyle.danger, custom_id="lock_room")
    async def lock_room(self, interaction: discord.Interaction, button: Button):
        overwrite = self.voice_channel.overwrites_for(interaction.guild.default_role)
        overwrite.connect = False
        await self.voice_channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔒 تم إغلاق الروم الصوتي بنجاح، لا يمكن لأحد الدخول الآن.", ephemeral=True)

    @discord.ui.button(label="🔓 فتح الروم", style=discord.ButtonStyle.success, custom_id="unlock_room")
    async def unlock_room(self, interaction: discord.Interaction, button: Button):
        overwrite = self.voice_channel.overwrites_for(interaction.guild.default_role)
        overwrite.connect = True
        await self.voice_channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔓 تم فتح الروم الصوتي للجميع.", ephemeral=True)

    @discord.ui.button(label="👁️ إخفاء الروم", style=discord.ButtonStyle.secondary, custom_id="hide_room")
    async def hide_room(self, interaction: discord.Interaction, button: Button):
        overwrite = self.voice_channel.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = False
        await self.voice_channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("👁️ تم إخفاء الروم الصوتي عن الجميع.", ephemeral=True)

    @discord.ui.button(label="🌟 إظهار الروم", style=discord.ButtonStyle.primary, custom_id="show_room")
    async def show_room(self, interaction: discord.Interaction, button: Button):
        overwrite = self.voice_channel.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = True
        await self.voice_channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🌟 تم إظهار الروم الصوتي للجميع.", ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    # 1. حالة دخول العضو إلى الروم الرئيسي لإنشاء روم مؤقت
    if after.channel and after.channel.id == MAIN_VOICE_CHANNEL_ID:
        guild = member.guild
        category = after.channel.category # إنشاء الروم في نفس القسم

        # صلاحيات الروم الصوتي (لصاحب الروم كامل الحرية وللباقي عادي)
        voice_overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
            member: discord.PermissionOverwrite(connect=True, view_channel=True, move_members=True)
        }

        # إنشاء الروم الصوتي المؤقت
        voice_channel = await guild.create_voice_channel(
            name=f"🎙️｜{member.display_name}",
            category=category,
            overwrites=voice_overwrites
        )

        # صلاحيات الشات الكتابي (مخفي عن الجميع ما عدا صاحب الروم والبوت)
        text_overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        # إنشاء الشات الكتابي المؤقت التابع للروم
        text_channel = await guild.create_text_channel(
            name=f"💬-تحكم-{member.display_name}",
            category=category,
            overwrites=text_overwrites
        )

        # نقل العضو تلقائياً إلى الروم الصوتي الجديد
        await member.move_to(voice_channel)

        # حفظ بيانات الروم في الذاكرة
        temp_rooms[voice_channel.id] = {
            "owner_id": member.id,
            "text_channel_id": text_channel.id
        }

        # إرسال رسالة التحكم والأزرار داخل الشات المؤقت
        embed = discord.Embed(
            title="🎮 لوحة تحكم الروم المؤقت",
            description=f"أهلاً بك يا {member.mention} في شات التحكم الخاص برومك الصوتي.\nيمكنك إدارة رومك بالكامل باستخدام الأزرار أدناه:",
            color=discord.Color.purple()
        )
        embed.add_field(name="الروم الصوتي:", value=voice_channel.mention, inline=True)
        embed.add_field(name="صاحب الروم:", value=member.mention, inline=True)
        
        view = RoomControlView(voice_channel, text_channel, member)
        await text_channel.send(embed=embed, view=view)

    # 2. حالة خروج العضو من الروم المؤقت (لحذف الروم والشات إذا أصبح فارغاً)
    if before.channel and before.channel.id in temp_rooms:
        voice_channel = before.channel
        # التأكد إذا كان الروم أصبح فارغاً تماماً من الأعضاء
        if len(voice_channel.members) == 0:
            room_data = temp_rooms[voice_channel.id]
            text_channel = bot.get_channel(room_data["text_channel_id"])
            
            # حذف الروم الصوتي والشات الكتابي
            try:
                await voice_channel.delete()
                if text_channel:
                    await text_channel.delete()
            except Exception as e:
                print(f"حدث خطأ أثناء حذف الرومات المتروكة: {e}")
                
            # إزالة الروم من الذاكرة
            del temp_rooms[voice_channel.id]

# جلب التوكن وتشغيل البوت
token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("❌ خطأ: لم يتم العثور على المتغير DISCORD_TOKEN في إعدادات Railway!")
