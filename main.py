import codecs
import logging
import os
import pickle
import uuid
from typing import Tuple, Dict, Optional, List

import discord
from discord import Role, TextChannel, Guild
from discord.ext import commands
from discord.ext.commands import Context, Bot

from settings import TOKEN, ADMIN_IDS, INIT_PW

CONFIG_FILE: str = 'configs/{}.pkl'
MASTER_ROLES_HANDLE: str = 'master_roles'
STUDENT_ROLES_HANDLE: str = 'student_roles'
ROLES_MAPPING_HANDLE: str = 'master_student_mapping'

# logger
log = logging.getLogger()
log.setLevel(level=logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh = logging.FileHandler('rolebot.log')
fh.setLevel(level=logging.INFO)
fh.setFormatter(formatter)
log.addHandler(fh)
ch = logging.StreamHandler()
ch.setLevel(level=logging.DEBUG)
ch.setFormatter(formatter)
log.addHandler(ch)


async def load_config(guild_id: str) -> Dict:
    global CONFIG_FILE
    local_config_file = CONFIG_FILE.format(guild_id)
    if os.path.exists(local_config_file):
        with codecs.open(local_config_file, 'rb') as f:
            config = pickle.load(f)
    else:
        config = {}
    log.info(f'LOADING GUILD CONFIG {guild_id}: {config}')
    return config


async def init_guild_config(guild_id: str) -> Dict:
    global CONFIG_FILE
    CONFIG_FILE = CONFIG_FILE.format(guild_id)
    config = {
        MASTER_ROLES_HANDLE: {},
        STUDENT_ROLES_HANDLE: [],
        ROLES_MAPPING_HANDLE: {}
    }
    await save_config(guild_id, config)
    return config


async def save_config(guild_id: str, config: Dict) -> None:
    global CONFIG_FILE
    CONFIG_FILE = CONFIG_FILE.format(guild_id)
    with codecs.open(CONFIG_FILE, 'wb') as f:
        pickle.dump(config, f)


# Create bot
intents = discord.Intents.default()
intents.members = True
client: Bot = commands.Bot(intents=intents, command_prefix='!')


# Startup Information
@client.event
async def on_ready() -> None:
    log.info(f'Connected to bot: {client.user.name}')
    log.info(f'Bot ID: {client.user.id}')


@client.command()
async def passwort(ctx: Context, *args) -> None:
    log.info(f'passwort - {ctx.author}')
    await ctx.message.delete()
    if len(ctx.message.role_mentions) == 0:
        await ctx.author.send(
            'Bitte benenne eine Rolle um ihr Passwort zu ändern.\n```!passwort <neues_passwort> @meister-rolle```')
        log.info(f'passwort - {ctx.author} - NOK 1')
        return
    role = ctx.message.role_mentions[0]
    pw = str(args[0])
    if pw == str(role.mention):
        pw = str(args[1])
    config = await load_config(ctx.guild.id)
    if int(role.id) not in config[MASTER_ROLES_HANDLE]:
        await ctx.author.send(
            'Du kannst nur Passwörter für Meister-Rollen verändern.\n```!passwort <neues_passwort> @meister-rolle```')
        log.info(f'passwort - {ctx.author} - NOK 2')
        return
    config[MASTER_ROLES_HANDLE][int(role.id)] = str(pw)
    await save_config(str(ctx.guild.id), config)
    await ctx.author.send(f'Habe das Passwort für {role.name} auf `{pw}` geändert.')
    log.info(f'passwort - {ctx.author} - OK')
    return


@client.command()
async def init(ctx: Context, *args) -> None:
    log.info(f'init - {ctx.author} - {ctx.message.content}')
    await ctx.message.delete()

    if ctx.author.id not in ADMIN_IDS:
        return
    if type(ctx.channel) is not TextChannel:
        await ctx.send(
            'Bitte nutze diese Funktion in einem Text Channel des Servers für den du die Rollenbeziehungen einrichten willst.')
        return

    error_msg = 'Ich bin verwirrt!\n{}\n\nBitte nenne mir eine Liste der Meister-Lehrling Rollen! Ich hätte sie gerne in diesem Format:\n```!init <passwort> @Meisterrolle1 @Lehrlingsrolle1 @Meisterrolle2 @Lehrlingsrolle2 ...```'

    if len(ctx.message.raw_role_mentions) == 0:
        await ctx.send(error_msg.format('Du hast mir keine Rollen gegeben!'))
        return

    if len(args) == 0:
        await ctx.send('Falsches Passwort ;)')
        return

    if args[0] != INIT_PW:
        await ctx.send('Falsches Passwort ;)')
        return
    config = await init_guild_config(ctx.guild.id)

    if len(ctx.message.raw_role_mentions) % 2 != 0:
        await ctx.send(error_msg.format(
            'Du hast mir eine falsche Anzahl an Rollen gegeben! Bitte alle Beziehungen immer in Meister-Lehrling-Paaren angeben.'))
        return

    role_pairs = []
    first = None
    for role_mention in ctx.message.raw_role_mentions:
        role = ctx.guild.get_role(role_mention)
        if not role:
            await ctx.send(error_msg.format(
                f'Diese Rolle des {role_mention} mir nicht bekannt.'))
            return
        else:
            if not first:
                first = role
            else:
                role_pairs.append((first, role))
                first = None

    for master_role, student_role in role_pairs:
        config[MASTER_ROLES_HANDLE][int(master_role.id)] = uuid.uuid4()
        config[STUDENT_ROLES_HANDLE].append(int(student_role.id))
        config[ROLES_MAPPING_HANDLE][int(master_role.id)] = int(student_role.id)

    await save_config(ctx.guild.id, config)
    await ctx.author.send('\n'.join(['**Folgende Rollenzuweisungen wurden gemacht:**', '```'] + [
        f'• {ctx.guild.get_role(k).name} -> {ctx.guild.get_role(config[ROLES_MAPPING_HANDLE][k]).name}'
        for k in config[ROLES_MAPPING_HANDLE]
    ] + ['```']))
    await ctx.author.send('\n'.join(
        ['**Bitte gib folgende Passwörter an die Elementarmeister weiter:**'] +
        [f'• {ctx.guild.get_role(k).name}: `{config[MASTER_ROLES_HANDLE][k]}`' for k in
         config[MASTER_ROLES_HANDLE]]
    ))


@client.command()
async def reset(ctx: Context) -> None:
    log.info(f'reset - {ctx.author} - {ctx.message.content}')
    if ctx.author.id not in ADMIN_IDS:
        return
    await ctx.message.delete()
    await init_guild_config(ctx.guild.id)
    await ctx.author.send(
        'Die komplette Konfiguration für diesen Server wurde resettet. Bitte füge neue Meister-Studenten Beziehungen hinzu indem du folgenden Befehl ausführst:\n```!init <passwort> @Meisterrolle1 @Lehrlingsrolle1 @Meisterrolle2 @Lehrlingsrolle2 ...```')


@client.command()
async def meister(ctx: Context, *args) -> None:
    log.info(f'meister - {ctx.author} - {ctx.message.content}')
    # IF COMMUNICATION HAPPENED IN A NON-DIRECT CHAT, REMOVE MESSAGE AS IT CONTAINS THE PW
    if type(ctx.channel) is TextChannel:
        await ctx.message.delete()
        await ctx.author.send(
            'Ich habe deine Nachricht aus dem allgemeinen Chat gelöscht, damit das Passwort nicht von anderen benutzt werden kann. Bitte sei in Zukunft etwas vorsichtiger!')

    # MAKE SOMEONE MASTER
    arguments: Tuple = args
    if len(arguments) == 0:
        await ctx.author.send(
            'Bitte nutze das Passwort um dich als Meister zu erkennen zu geben! Beispiel:\n```!meister mein-super-geheimes-passwort```')
        return

    user_pw: str = arguments[0]

    added_on: List[Tuple[str, str]] = []
    log.info(f'CLIENT GUILDS: {client.guilds}')
    for guild in client.guilds:
        member = guild.get_member(ctx.author.id)
        log.info(f'GUILD HAS MEMBER {ctx.author.id}: {guild} - {member}')
        if not member:
            continue
        guild_config = await load_config(guild.id)

        matches_master_pw: List[Tuple[int, bool]] = [
            (int(role), str(guild_config[MASTER_ROLES_HANDLE][role]) == user_pw) for role in
            guild_config[MASTER_ROLES_HANDLE]]
        for role_id, matches in matches_master_pw:
            if matches:
                role: Role = guild.get_role(role_id)
                if not role:
                    continue
                await member.add_roles(role)
                added_on.append((guild.name, role.name))

    if len(added_on) == 0:
        await ctx.author.send(
            f'Ich konnte dieses Passwort leider keinem Server zuordnen. Bist du sicher, dass es korrekt ist?')
    else:
        for details in added_on:
            await ctx.author.send(
                f'Du wurdest auf dem Server **{details[0]}** in den Stand des **{details[1]}s** erhoben!')
    return


@client.command()
async def lehrling(ctx: Context):
    log.info(f'lehrling - {ctx.author} - {ctx.message.content}')
    # MAKE LIST OF PEOPLE PUPILS
    if len(ctx.message.mentions) == 0:
        await ctx.author.send(
            'Du musst mindestens einen Lehrling angeben! Beispiele:\n```!lehrling @Andabar\n!lehrling @Andabar @Sonderbar```')
        return

    identified_master_role: Optional[Role] = None
    identified_guild: Optional[Guild] = None
    identified_config: Optional[Dict] = None
    for guild in client.guilds:
        member = guild.get_member(ctx.author.id)
        if not member:
            continue
        guild_config = await load_config(guild.id)

        for role in member.roles:
            for master_role_id in guild_config[MASTER_ROLES_HANDLE]:
                if int(role.id) == master_role_id:
                    identified_master_role = role
                    identified_guild = guild
                    identified_config = guild_config
                    break
            if identified_master_role is not None:
                break
        if identified_master_role is not None:
            break

    if not identified_master_role:
        await ctx.author.send('Nur Meister können Lehrlinge aufnehmen, aber du bist kein Meister!')
        return

    identified_students = []
    for student_mention in ctx.message.mentions:
        student = identified_guild.get_member(student_mention.id)
        if not student:
            await ctx.author.send(
                f'Ich konnte leider keinen Lehrling namens {student_mention} auf **{identified_guild.name}** ausfindig machen.')
            continue
        else:
            identified_students.append(student)

    student_role = identified_guild.get_role(identified_config[ROLES_MAPPING_HANDLE][identified_master_role.id])
    if not student_role:
        await ctx.author.send(
            f'Ich konnte leider die Lehrlingsrolle nicht finden, was auf ein technisches Problem hinweist - Bitte wende dich an einen der Organisatoren!.')

    for student in identified_students:
        await student.add_roles(student_role)

    if len(identified_students) == 1:
        await ctx.author.send(
            f'Ich habe aus {identified_students[0].mention} einen {student_role.name} gemacht.')
    else:
        await ctx.author.send(
            f'Ich habe {" ".join([s.mention for s in identified_students])} zu {student_role.name}en gemacht.')


# Run the bot
client.run(TOKEN)
