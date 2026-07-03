import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import json
import os
import datetime
import random
import asyncio

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)

ARCHIVO_BIENVENIDAS = "config_bienvenidas.json"
ARCHIVO_DESPEDIDAS = "config_despedidas.json"
ARCHIVO_INVITES = "datos_invites.json"
ARCHIVO_BOOSTS = "config_boosts.json"
ARCHIVO_ENCUESTAS = "encuestas_activas.json"

COLORES_ENCUESTA = [0x5865F2, 0xED4245, 0x57F287, 0xFEE75C, 0xEB459E, 0x99AAB5, 0x2b2d31, 0xF47B67, 0x9B59B6]

def cargar_json(archivo):
    if not os.path.exists(archivo):
        return {}
    with open(archivo, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_json(archivo, datos):
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)

def cargar_invites():
    if not os.path.exists(ARCHIVO_INVITES):
        return {"CONFIG": {}, "STATS": {}, "CACHE": {}, "MAP": {}}
    with open(ARCHIVO_INVITES, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_invites(datos):
    with open(ARCHIVO_INVITES, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)

def reemplazar_variables(texto, servidor, usuario):
    if not texto:
        return texto
    texto = texto.replace("{server}", servidor.name)
    texto = texto.replace("{user}", usuario.mention)
    return texto

async def logica_invites(origen, usuario):
    if not usuario:
        if isinstance(origen, discord.Interaction):
            usuario = origen.user
        else:
            usuario = origen.author
            
    datos = cargar_invites()
    gid = str(origen.guild.id)
    uid = str(usuario.id)
    
    stats = datos["STATS"].get(gid, {}).get(uid, {"total": 0, "left": 0, "fakes": 0})
    total = stats["total"]
    left = stats["left"]
    fakes = stats["fakes"]
    validos = total - left - fakes

    embed = discord.Embed(title=f"Invitaciones de {usuario.name}", color=0x2b2d31)
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="━━━  Estadísticas  ━━━", value=f"**Total:** {total}\n**Válidos:** {validos}\n**Se salieron:** {left}\n**Falsos (< 7 días):** {fakes}", inline=False)
    return embed

async def logica_lb_invites(origen):
    datos = cargar_invites()
    gid = str(origen.guild.id)
    stats_guild = datos["STATS"].get(gid, {})
    
    if not stats_guild:
        return None

    top = sorted(stats_guild.items(), key=lambda x: x[1]["total"], reverse=True)[:10]
    embed = discord.Embed(title="Top 10 Invites", description="Los usuarios con más invitaciones en el servidor.\n", color=0x2b2d31)
    
    lista_texto = ""
    for i, (uid, stats) in enumerate(top):
        miembro = origen.guild.get_member(int(uid))
        nombre = miembro.display_name if miembro else f"Usuario Desconocido"
        medalla = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**#{i+1}**"
        linea = f"> {medalla} **{nombre}**\n> ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n>  ↳ `{stats['total']}` invitaciones totales\n\n"
        lista_texto += linea

    embed.description = lista_texto
    return embed

@bot.event
async def on_ready():
    print(f"Conectado como {bot.user}")
    datos = cargar_invites()
    for guild in bot.guilds:
        gid = str(guild.id)
        datos["CACHE"][gid] = {}
        try:
            invites = await guild.invites()
            for inv in invites:
                datos["CACHE"][gid][inv.code] = inv.uses
        except Exception:
            pass
    guardar_invites(datos)
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} comandos sincronizados correctamente.")
    except Exception as e:
        print(f"Error al sincronizar: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.content.lower() == "ian":
        await message.channel.send("Ian, mi dueño.... Me trata mal we")
    await bot.process_commands(message)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    datos = cargar_json(ARCHIVO_ENCUESTAS)
    if str(payload.message_id) in datos:
        try:
            canal = bot.get_channel(payload.channel_id)
            mensaje = await canal.fetch_message(payload.message_id)
            await mensaje.remove_reaction(payload.emoji, discord.Object(payload.user_id))
        except Exception:
            pass

@bot.tree.command(name="config-invites", description="Configura el canal y el mensaje de las invitaciones (Solo Admins)")
@app_commands.describe(canal="Canal donde se enviará el mensaje de invitación", texto="Mensaje (usa {user}, {autor}, {servidor}, {invites})")
async def config_invites(interaction: discord.Interaction, canal: discord.TextChannel, texto: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Solo los administradores pueden usar este comando.", ephemeral=True)
    if not canal:
        return await interaction.response.send_message("El canal seleccionado no es válido.", ephemeral=True)

    datos = cargar_invites()
    datos["CONFIG"][str(interaction.guild.id)] = {"canal": canal.id, "texto": texto}
    guardar_invites(datos)

    texto_preview = texto.replace("{user}", interaction.user.mention).replace("{autor}", interaction.user.mention).replace("{servidor}", interaction.guild.name).replace("{invites}", "0")
    await interaction.response.send_message(f"✅ Sistema configurado en {canal.mention}. Así se verá:\n\n{texto_preview}", ephemeral=True)

@bot.tree.command(name="invites", description="Mira las estadísticas de invitaciones de un usuario")
@app_commands.describe(usuario="El usuario a revisar (por defecto tú mismo)")
async def invites_slash(interaction: discord.Interaction, usuario: discord.Member = None):
    embed = await logica_invites(interaction, usuario)
    await interaction.response.send_message(embed=embed)

@bot.command(name="invites")
async def invites_prefix(ctx, usuario: discord.Member = None):
    embed = await logica_invites(ctx, usuario)
    if embed:
        await ctx.send(embed=embed)

@bot.tree.command(name="lb-invites", description="Top 10 de usuarios con más invitaciones totales")
async def lb_invites_slash(interaction: discord.Interaction):
    embed = await logica_lb_invites(interaction)
    if embed:
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("No hay datos de invitaciones en este servidor todavía.", ephemeral=True)

@bot.command(name="lb-invites", aliases=["lb_invites"])
async def lb_invites_prefix(ctx):
    embed = await logica_lb_invites(ctx)
    if embed:
        await ctx.send(embed=embed)
    else:
        await ctx.send("No hay datos de invitaciones en este servidor todavía.")

@bot.tree.command(name="config-bienvenidas", description="Configura el embed y el canal de bienvenidas")
@app_commands.describe(canal="El canal donde llegarán las bienvenidas", color="ID del color exacto en HEX (ej: #ff0000)", titulo="Título del embed (usa {server} o {user})", descripcion="Descripción del embed (usa {server} o {user})", texto="Texto opcional fuera del embed", imagen="Enlace de la imagen (URL) para el banner (opcional)", thumbnail="True para mostrar la foto del usuario al costado derecho, False para ocultarla")
async def config_bienvenidas(interaction: discord.Interaction, canal: discord.TextChannel, color: str, titulo: str, descripcion: str, texto: str = None, imagen: str = None, thumbnail: bool = True):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Solo los administradores pueden usar este comando.", ephemeral=True)
    if not canal:
        return await interaction.response.send_message("El canal seleccionado no es válido.", ephemeral=True)

    try:
        color_procesado = discord.Color.from_str(color)
    except ValueError:
        return await interaction.response.send_message("El color no es válido. Usa un formato HEX exacto.", ephemeral=True)

    config = cargar_json(ARCHIVO_BIENVENIDAS)
    config[str(interaction.guild.id)] = {"canal": canal.id, "color": color, "titulo": titulo, "descripcion": descripcion, "texto": texto, "imagen": imagen, "thumbnail": thumbnail}
    guardar_json(ARCHIVO_BIENVENIDAS, config)

    titulo_preview = reemplazar_variables(titulo, interaction.guild, interaction.user)
    desc_preview = reemplazar_variables(descripcion, interaction.guild, interaction.user)
    texto_preview = reemplazar_variables(texto, interaction.guild, interaction.user)

    embed_preview = discord.Embed(title=titulo_preview, description=desc_preview, color=color_procesado)
    if thumbnail:
        embed_preview.set_thumbnail(url=interaction.user.display_avatar.url)
    if imagen:
        embed_preview.set_image(url=imagen)

    respuesta = f"✅ Sistema configurado en {canal.mention}. Así se verá:"
    if texto_preview:
        respuesta = f"{texto_preview}\n{respuesta}"
    await interaction.response.send_message(respuesta, embed=embed_preview, ephemeral=True)

@bot.tree.command(name="config-despedidas", description="Configura el embed y el canal de despedidas")
@app_commands.describe(canal="El canal donde llegarán las despedidas", color="ID del color exacto en HEX (ej: #ff0000)", titulo="Título del embed (usa {server} o {user})", descripcion="Descripción del embed (usa {server} o {user})", texto="Texto opcional fuera del embed", imagen="Enlace de la imagen (URL) para el banner (opcional)", thumbnail="True para mostrar la foto del usuario al costado derecho, False para ocultarla")
async def config_despedidas(interaction: discord.Interaction, canal: discord.TextChannel, color: str, titulo: str, descripcion: str, texto: str = None, imagen: str = None, thumbnail: bool = True):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Solo los administradores pueden usar este comando.", ephemeral=True)
    if not canal:
        return await interaction.response.send_message("El canal seleccionado no es válido.", ephemeral=True)

    try:
        color_procesado = discord.Color.from_str(color)
    except ValueError:
        return await interaction.response.send_message("El color no es válido. Usa un formato HEX exacto.", ephemeral=True)

    config = cargar_json(ARCHIVO_DESPEDIDAS)
    config[str(interaction.guild.id)] = {"canal": canal.id, "color": color, "titulo": titulo, "descripcion": descripcion, "texto": texto, "imagen": imagen, "thumbnail": thumbnail}
    guardar_json(ARCHIVO_DESPEDIDAS, config)

    titulo_preview = reemplazar_variables(titulo, interaction.guild, interaction.user)
    desc_preview = reemplazar_variables(descripcion, interaction.guild, interaction.user)
    texto_preview = reemplazar_variables(texto, interaction.guild, interaction.user)

    embed_preview = discord.Embed(title=titulo_preview, description=desc_preview, color=color_procesado)
    if thumbnail:
        embed_preview.set_thumbnail(url=interaction.user.display_avatar.url)
    if imagen:
        embed_preview.set_image(url=imagen)

    respuesta = f"✅ Sistema de despedidas configurado en {canal.mention}. Así se verá:"
    if texto_preview:
        respuesta = f"{texto_preview}\n{respuesta}"
    await interaction.response.send_message(respuesta, embed=embed_preview, ephemeral=True)

@bot.tree.command(name="config-boost", description="Configura el embed y canal para cuando alguien boostee el servidor")
@app_commands.describe(canal="El canal donde llegarán los mensajes de boost", color="ID del color exacto en HEX (ej: #ff69b4)", titulo="Título del embed (usa {user} o {server})", descripcion="Descripción del embed (usa {user} o {server})", texto="Texto opcional fuera del embed", footer="Texto que irá en la parte inferior del embed", imagen="Enlace de la imagen (URL) para el banner (opcional)", thumbnail="True para mostrar la foto del usuario al costado, False para ocultarla")
async def config_boost(interaction: discord.Interaction, canal: discord.TextChannel, color: str, titulo: str, descripcion: str, texto: str = None, footer: str = None, imagen: str = None, thumbnail: bool = False):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Solo los administradores pueden usar este comando.", ephemeral=True)
    if not canal:
        return await interaction.response.send_message("El canal seleccionado no es válido.", ephemeral=True)

    try:
        color_procesado = discord.Color.from_str(color)
    except ValueError:
        return await interaction.response.send_message("El color no es válido. Usa un formato HEX exacto.", ephemeral=True)

    config = cargar_json(ARCHIVO_BOOSTS)
    config[str(interaction.guild.id)] = {"canal": canal.id, "color": color, "titulo": titulo, "descripcion": descripcion, "texto": texto, "footer": footer, "imagen": imagen, "thumbnail": thumbnail}
    guardar_json(ARCHIVO_BOOSTS, config)

    titulo_preview = reemplazar_variables(titulo, interaction.guild, interaction.user)
    desc_preview = reemplazar_variables(descripcion, interaction.guild, interaction.user)
    texto_preview = reemplazar_variables(texto, interaction.guild, interaction.user)

    embed_preview = discord.Embed(title=titulo_preview, description=desc_preview, color=color_procesado)
    if footer:
        embed_preview.set_footer(text=footer)
    if thumbnail:
        embed_preview.set_thumbnail(url=interaction.user.display_avatar.url)
    if imagen:
        embed_preview.set_image(url=imagen)

    resposta = f"✅ Sistema de boosts configurado en {canal.mention}. Así se verá:"
    if texto_preview:
        resposta = f"{texto_preview}\n{resposta}"
    await interaction.response.send_message(resposta, embed=embed_preview, ephemeral=True)

@bot.tree.command(name="embed", description="Envía un embed personalizado a cualquier canal")
@app_commands.describe(canal="El canal donde se enviará el embed", color="ID del color exacto en HEX (ej: #00ff00)", titulo="Título del embed", descripcion="Descripción del embed", texto="Texto opcional que se enviará fuera del embed", footer="Texto que irá en la parte inferior del embed", imagen="Enlace de la imagen (URL) para el banner (opcional)")
async def embed_personalizado(interaction: discord.Interaction, canal: discord.TextChannel, color: str, titulo: str, descripcion: str, texto: str = None, footer: str = None, imagen: str = None):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("Necesitas permisos para gestionar mensajes.", ephemeral=True)
    if not canal:
        return await interaction.response.send_message("El canal seleccionado no es válido.", ephemeral=True)

    try:
        color_procesado = discord.Color.from_str(color)
    except ValueError:
        return await interaction.response.send_message("El color no es válido. Usa un formato HEX exacto.", ephemeral=True)

    embed = discord.Embed(title=titulo, description=descripcion, color=color_procesado)
    if footer:
        embed.set_footer(text=footer)
    if imagen:
        embed.set_image(url=imagen)

    if texto:
        await canal.send(texto)
    await canal.send(embed=embed)
    await interaction.response.send_message(f"✅ Embed enviado correctamente a {canal.mention}.", ephemeral=True)

@bot.tree.command(name="say", description="Haz que el bot diga un mensaje (Solo Admins)")
@app_commands.describe(texto="El texto que quieres que el bot envíe")
async def say_slash(interaction: discord.Interaction, texto: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Solo los administradores pueden usar este comando.", ephemeral=True)
    
    await interaction.response.send_message("✅ Mensaje enviado.", ephemeral=True)
    await interaction.channel.send(texto)

@bot.command(name="say")
async def say_prefix(ctx, *, texto: str):
    if not ctx.author.guild_permissions.administrator:
        try:
            await ctx.message.delete()
        except Exception:
            pass
        try:
            await ctx.author.send("No tienes permisos de administrador para usar el comando `?say`.", delete_after=5)
        except Exception:
            pass
        return

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await ctx.send(texto)

class EncuestaView(View):
    def __init__(self, opciones, multiples, color):
        super().__init__(timeout=None)
        self.opciones = opciones
        self.multiples = multiples
        self.color = color
        self.votos = {str(i): [] for i in range(len(opciones))}
        
        for i, opcion in enumerate(opciones):
            self.add_item(Button(label=opcion, style=discord.ButtonStyle.secondary, custom_id=f"op_{i}"))
        
        self.add_item(Button(emoji="🔒", style=discord.ButtonStyle.danger, custom_id="op_finalizar"))
        self.add_item(Button(emoji="❌", style=discord.ButtonStyle.danger, custom_id="op_cancelar"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] in ["op_finalizar", "op_cancelar"]:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Solo los administradores pueden usar estos botones.", ephemeral=True)
                return False
        return True

    async def actualizar_embed(self, interaction):
        total_votos = sum(len(v) for v in self.votos.values())
        nueva_desc = ""
        
        for i, opcion in enumerate(self.opciones):
            cantidad = len(self.votos[str(i)])
            porcentaje = (cantidad / total_votos * 100) if total_votos > 0 else 0
            
            barra_len = 15
            barra_llena = int(barra_len * (porcentaje / 100))
            barra_vacia = barra_len - barra_llena
            barra = "█" * barra_llena + "░" * barra_vacia
            
            nueva_desc += f"**{opcion}**\n┃{barra}┃ **{porcentaje:.1f}%** · *({cantidad} votos)*\n\n"
            
        estado_texto = "🔒 FINALIZADA" if self.disabled_voting else ("Múltiples respuestas" if self.multiples else "Respuesta única")
        
        nuevo_embed = discord.Embed(title=interaction.message.embeds[0].title, description=nueva_desc, color=self.color)
        nuevo_embed.set_footer(text=f"{estado_texto} • Total: {total_votos} votos")
        
        await interaction.message.edit(embed=nuevo_embed, view=self)

    @discord.ui.button(emoji="🔒", style=discord.ButtonStyle.danger, custom_id="op_finalizar")
    async def boton_finalizar(self, interaction: discord.Interaction, button: Button):
        if hasattr(self, 'disabled_voting') and self.disabled_voting:
            return
        self.disabled_voting = True
        for child in self.children:
            if child.custom_id.startswith("op_") and child.custom_id not in ["op_finalizar", "op_cancelar"]:
                child.disabled = True
        button.disabled = True
        await self.actualizar_embed(interaction)
        await interaction.response.send_message("✅ Encuesta finalizada correctamente.", ephemeral=True)

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.danger, custom_id="op_cancelar")
    async def boton_cancelar(self, interaction: discord.Interaction, button: Button):
        if hasattr(self, 'cancelada') and self.cancelada:
            return
        self.cancelada = True
        for child in self.children:
            child.disabled = True
            
        embed_cancelado = discord.Embed(title="❌ Encuesta Cancelada", description="Esta encuesta ha sido cancelada por un administrador y se eliminará pronto.", color=discord.Color.red())
        await interaction.message.edit(embed=embed_cancelado, view=self)
        await interaction.response.send_message("Encuesta cancelada. Se eliminará en 10 segundos.", ephemeral=True)
        
        await asyncio.sleep(10)
        try:
            await interaction.message.delete()
            datos = cargar_json(ARCHIVO_ENCUESTAS)
            if str(interaction.message.id) in datos:
                del datos[str(interaction.message.id)]
                guardar_json(ARCHIVO_ENCUESTAS, datos)
        except Exception:
            pass

async def boton_opcion_callback(interaction: discord.Interaction):
    custom_id = interaction.data["custom_id"]
    if not custom_id.startswith("op_") or custom_id in ["op_finalizar", "op_cancelar"]:
        return

    view = interaction.message.components[0]
    view_obj = None
    for v in bot._views:
        if isinstance(v, EncuestaView):
            for item in v.children:
                if item.custom_id == custom_id:
                    view_obj = v
                    break
            if view_obj:
                break

    if not view_obj:
        return

    if hasattr(view_obj, 'cancelada') and view_obj.cancelada:
        return

    if hasattr(view_obj, 'disabled_voting') and view_obj.disabled_voting:
        await interaction.response.send_message("La encuesta ya está finalizada, no puedes cambiar tu voto.", ephemeral=True)
        return

    indice = custom_id.split("_")[1]
    usuario_id = str(interaction.user.id)

    if not view_obj.multiples:
        for key, lista_votos in view_obj.votos.items():
            if usuario_id in lista_votos and key != indice:
                lista_votos.remove(usuario_id)

    if usuario_id in view_obj.votos[indice]:
        view_obj.votos[indice].remove(usuario_id)
        await interaction.response.send_message("Se quitó tu voto correctamente.", ephemeral=True)
    else:
        view_obj.votos[indice].append(usuario_id)
        await interaction.response.send_message("Voto registrado correctamente.", ephemeral=True)

    await view_obj.actualizar_embed(interaction)

bot.add_listener(boton_opcion_callback, name='on_interaction')

@bot.tree.command(name="encuesta", description="Crea una encuesta interactiva con botones (Solo Admins)")
@app_commands.describe(pregunta="La pregunta o título de la encuesta", opcion1="Primera opción", opcion2="Segunda opción", opcion3="Tercera opción (opcional)", opcion4="Cuarta opción (opcional)", opcion5="Quinta opción (opcional)", multiples="True si quieren votar varias opciones, False para una sola")
async def encuesta_slash(interaction: discord.Interaction, pregunta: str, opcion1: str, opcion2: str, opcion3: str = None, opcion4: str = None, opcion5: str = None, multiples: bool = False):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Solo los administradores pueden usar este comando.", ephemeral=True)

    opciones = [opcion1, opcion2]
    if opcion3: opciones.append(opcion3)
    if opcion4: opciones.append(opcion4)
    if opcion5: opciones.append(opcion5)
    
    color_random = random.choice(COLORES_ENCUESTA)
    view = EncuestaView(opciones, multiples, color_random)
    
    tipo = "Múltiples respuestas" if multiples else "Respuesta única"
    embed = discord.Embed(title=f"📊  {pregunta}", description="*Haz clic en los botones para votar.*", color=color_random)
    embed.set_footer(text=f"{tipo} • Creada por {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed, view=view)
    mensaje = await interaction.original_response()
    
    datos = cargar_json(ARCHIVO_ENCUESTAS)
    datos[str(mensaje.id)] = {"estado": "activa"}
    guardar_json(ARCHIVO_ENCUESTAS, datos)

@bot.event
async def on_member_join(member):
    await procesar_bienvenida(member)
    await procesar_invite(member)

async def procesar_bienvenida(member):
    config = cargar_json(ARCHIVO_BIENVENIDAS)
    id_servidor = str(member.guild.id)

    if id_servidor in config:
        datos = config[id_servidor]
        canal = member.guild.get_channel(datos["canal"])

        if canal:
            try:
                color_procesado = discord.Color.from_str(datos["color"])
            except ValueError:
                color_procesado = discord.Color.blue()

            titulo_final = reemplazar_variables(datos["titulo"], member.guild, member)
            desc_final = reemplazar_variables(datos["descripcion"], member.guild, member)
            texto_final = reemplazar_variables(datos.get("texto"), member.guild, member)

            embed = discord.Embed(title=titulo_final, description=desc_final, color=color_procesado)

            if datos.get("thumbnail", datos.get("autor", True)):
                embed.set_thumbnail(url=member.display_avatar.url)
            if datos.get("imagen"):
                embed.set_image(url=datos["imagen"])

            if texto_final:
                await canal.send(texto_final)
            await canal.send(embed=embed)

async def procesar_despedida(member):
    config = cargar_json(ARCHIVO_DESPEDIDAS)
    id_servidor = str(member.guild.id)

    if id_servidor in config:
        datos = config[id_servidor]
        canal = member.guild.get_channel(datos["canal"])

        if canal:
            try:
                color_procesado = discord.Color.from_str(datos["color"])
            except ValueError:
                color_procesado = discord.Color.dark_red()

            titulo_final = reemplazar_variables(datos["titulo"], member.guild, member)
            desc_final = reemplazar_variables(datos["descripcion"], member.guild, member)
            texto_final = reemplazar_variables(datos.get("texto"), member.guild, member)

            embed = discord.Embed(title=titulo_final, description=desc_final, color=color_procesado)

            if datos.get("thumbnail", True):
                embed.set_thumbnail(url=member.display_avatar.url)
            if datos.get("imagen"):
                embed.set_image(url=datos["imagen"])

            if texto_final:
                await canal.send(texto_final)
            await canal.send(embed=embed)

async def procesar_invite(member):
    datos = cargar_invites()
    gid = str(member.guild.id)
    
    if gid not in datos["CACHE"]:
        datos["CACHE"][gid] = {}
        
    try:
        invites_actuales = await member.guild.invites()
    except Exception:
        invites_actuales = []

    invitador_id = None
    cuenta_encontrada = False

    for inv in invites_actuales:
        usos_antiguos = datos["CACHE"][gid].get(inv.code, 0)
        if inv.uses > usos_antiguos and not cuenta_encontrada:
            if inv.inviter:
                invitador_id = str(inv.inviter.id)
            cuenta_encontrada = True
        datos["CACHE"][gid][inv.code] = inv.uses

    fecha_actual = datetime.datetime.now(datetime.timezone.utc)
    siete_dias_atras = fecha_actual - datetime.timedelta(days=7)
    es_falso = member.created_at > siete_dias_atras

    if invitador_id:
        if gid not in datos["STATS"]:
            datos["STATS"][gid] = {}
        if invitador_id not in datos["STATS"][gid]:
            datos["STATS"][gid][invitador_id] = {"total": 0, "left": 0, "fakes": 0}

        datos["STATS"][gid][invitador_id]["total"] += 1
        if es_falso:
            datos["STATS"][gid][invitador_id]["fakes"] += 1

        if gid not in datos["MAP"]:
            datos["MAP"][gid] = {}
        datos["MAP"][gid][str(member.id)] = invitador_id

    if gid in datos["CONFIG"]:
        config = datos["CONFIG"][gid]
        canal = member.guild.get_channel(config["canal"])
        if canal:
            texto_final = config["texto"]
            texto_final = texto_final.replace("{user}", member.mention)
            texto_final = texto_final.replace("{servidor}", member.guild.name)
            
            if invitador_id:
                invitador = member.guild.get_member(int(invitador_id))
                texto_final = texto_final.replace("{autor}", invitador.mention if invitador else "Desconocido")
                total_invites = datos["STATS"][gid][invitador_id]["total"]
                texto_final = texto_final.replace("{invites}", str(total_invites))
            else:
                texto_final = texto_final.replace("{autor}", "Desconocido")
                texto_final = texto_final.replace("{invites}", "0")
                
            await canal.send(texto_final)

    guardar_invites(datos)

@bot.event
async def on_member_remove(member):
    await procesar_despedida(member)

@bot.event
async def on_raw_member_remove(payload):
    datos = cargar_invites()
    gid = str(payload.guild_id)

    if gid in datos["MAP"] and str(payload.user.id) in datos["MAP"][gid]:
        invitador_id = datos["MAP"][gid][str(payload.user.id)]
        if gid in datos["STATS"][gid] and invitador_id in datos["STATS"][gid]:
            datos["STATS"][gid][invitador_id]["left"] += 1
        del datos["MAP"][gid][str(payload.user.id)]
        guardar_invites(datos)

@bot.event
async def on_member_update(before, after):
    if before.premium_since is None and after.premium_since is not None:
        config = cargar_json(ARCHIVO_BOOSTS)
        id_servidor = str(after.guild.id)

        if id_servidor in config:
            datos = config[id_servidor]
            canal = after.guild.get_channel(datos["canal"])

            if canal:
                try:
                    color_procesado = discord.Color.from_str(datos["color"])
                except ValueError:
                    color_procesado = discord.Color.pink()

                titulo_final = reemplazar_variables(datos["titulo"], after.guild, after)
                desc_final = reemplazar_variables(datos["descripcion"], after.guild, after)
                texto_final = reemplazar_variables(datos.get("texto"), after.guild, after)

                embed = discord.Embed(title=titulo_final, description=desc_final, color=color_procesado)

                if datos.get("footer"):
                    embed.set_footer(text=datos["footer"])
                if datos.get("thumbnail", False):
                    embed.set_thumbnail(url=after.display_avatar.url)
                if datos.get("imagen"):
                    embed.set_image(url=datos["imagen"])

                if texto_final:
                    await canal.send(texto_final)
                await canal.send(embed=embed)

TOKEN = os.getenv("TOKEN")
bot.run(TOKEN)