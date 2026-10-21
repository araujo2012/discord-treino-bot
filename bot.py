"""Bot de sessão de treino para Discord.

Painel com botões (Treinar / Sair / Ausentar / Status) e comandos de admin
em /treino. Todas as respostas aos jogadores são efêmeras (só quem clicou vê).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # opcional: sincroniza comandos na hora nesse servidor
DATA_FILE = Path(__file__).with_name("data.json")
PANEL_COLOR = discord.Color.red()
NO_MENTIONS = discord.AllowedMentions.none()


class Store:
    """Estado por servidor, salvo em JSON para sobreviver a reinícios."""

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text("utf-8")) if path.exists() else {}

    def guild(self, guild_id: int) -> dict:
        return self.data.setdefault(
            str(guild_id), {"session": 1, "panel": None, "players": {}}
        )

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8")
        tmp.replace(self.path)


store = Store(DATA_FILE)


def panel_embed(g: dict) -> discord.Embed:
    players = g["players"]
    leaving = sum(p["leaving"] for p in players.values())
    lines = [
        f"**Sessão #{g['session']}**",
        "",
        f"**Jogadores no treino:** {len(players)}",
    ]
    if leaving:
        lines.append(f"**Saindo no fim da sessão:** {leaving}")
    embed = discord.Embed(
        title="Sessão de Treino",
        description="\n".join(lines),
        color=PANEL_COLOR,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="Atualizado")
    return embed


def status_embed(g: dict) -> discord.Embed:
    players = sorted(g["players"].items(), key=lambda item: item[1]["joined_at"])
    if players:
        lines = [
            f"{i}. <@{uid}>" + (" — sai no fim da sessão" if p["leaving"] else "")
            for i, (uid, p) in enumerate(players, start=1)
        ]
        description = "\n".join(lines)
        if len(description) > 4000:
            description = description[:4000] + "\n…"
    else:
        description = "Ninguém no treino ainda."
    return discord.Embed(
        title=f"Sessão #{g['session']} — {len(players)} jogador(es)",
        description=description,
        color=PANEL_COLOR,
    )


async def reply(interaction: discord.Interaction, content: str) -> None:
    await interaction.response.send_message(
        content, ephemeral=True, allowed_mentions=NO_MENTIONS
    )


async def refresh_panel(guild_id: int) -> None:
    """Atualiza o contador do painel publicado nesse servidor."""
    g = store.guild(guild_id)
    panel = g["panel"]
    if not panel:
        return
    channel = bot.get_channel(panel["channel_id"])
    if channel is None:
        return
    try:
        await channel.get_partial_message(panel["message_id"]).edit(embed=panel_embed(g))
    except discord.NotFound:
        g["panel"] = None
        store.save()
    except discord.HTTPException:
        pass


class TrainingView(discord.ui.View):
    """Botões do painel. custom_id fixo + timeout=None = continuam funcionando após reinício."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Treinar", style=discord.ButtonStyle.primary, custom_id="treino:entrar")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = store.guild(interaction.guild_id)
        player = g["players"].get(str(interaction.user.id))
        if player and player["leaving"]:
            player["leaving"] = False
            msg = "Ausência cancelada! Você continua no treino."
        elif player:
            await reply(interaction, "Você já está no treino!")
            return
        else:
            g["players"][str(interaction.user.id)] = {
                "joined_at": datetime.now(timezone.utc).isoformat(),
                "leaving": False,
            }
            msg = "Você entrou no treino!"
        store.save()
        await reply(interaction, msg)
        await refresh_panel(interaction.guild_id)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.danger, custom_id="treino:sair")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = store.guild(interaction.guild_id)
        if g["players"].pop(str(interaction.user.id), None) is None:
            await reply(interaction, "Você não está no treino!")
            return
        store.save()
        await reply(interaction, "Você saiu do treino.")
        await refresh_panel(interaction.guild_id)

    @discord.ui.button(label="Ausentar", style=discord.ButtonStyle.secondary, custom_id="treino:ausentar")
    async def away(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = store.guild(interaction.guild_id)
        player = g["players"].get(str(interaction.user.id))
        if player is None:
            await reply(interaction, "Você não está no treino!")
            return
        player["leaving"] = not player["leaving"]
        store.save()
        if player["leaving"]:
            msg = "Você vai sair do treino no fim desta sessão. Clique de novo para cancelar."
        else:
            msg = "Ausência cancelada! Você continua no treino."
        await reply(interaction, msg)
        await refresh_panel(interaction.guild_id)

    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, custom_id="treino:status")
    async def status(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = store.guild(interaction.guild_id)
        await interaction.response.send_message(
            embed=status_embed(g), ephemeral=True, allowed_mentions=NO_MENTIONS
        )


treino = app_commands.Group(
    name="treino",
    description="Administração da sessão de treino",
    guild_only=True,
    default_permissions=discord.Permissions(manage_guild=True),
)


@treino.command(name="painel", description="Publica o painel de treino neste canal")
async def cmd_panel(interaction: discord.Interaction):
    g = store.guild(interaction.guild_id)
    old = g["panel"]
    try:
        message = await interaction.channel.send(embed=panel_embed(g), view=TrainingView())
    except discord.HTTPException:
        await reply(interaction, "Não consegui enviar mensagem aqui. Confira as permissões do bot neste canal.")
        return
    # Mantém só um painel ativo por servidor.
    if old:
        old_channel = bot.get_channel(old["channel_id"])
        if old_channel is not None:
            try:
                await old_channel.get_partial_message(old["message_id"]).delete()
            except discord.HTTPException:
                pass
    g["panel"] = {"channel_id": message.channel.id, "message_id": message.id}
    store.save()
    await reply(interaction, "Painel publicado!")


@treino.command(name="encerrar", description="Encerra a sessão atual e remove quem pediu para se ausentar")
async def cmd_end(interaction: discord.Interaction):
    g = store.guild(interaction.guild_id)
    leaving = [uid for uid, p in g["players"].items() if p["leaving"]]
    for uid in leaving:
        del g["players"][uid]
    ended = g["session"]
    g["session"] += 1
    store.save()
    if leaving:
        removed = ", ".join(f"<@{uid}>" for uid in leaving)
        summary = f"Saíram ({len(leaving)}): {removed}"
    else:
        summary = "Ninguém tinha pedido para sair."
    await reply(
        interaction,
        f"Sessão #{ended} encerrada. {summary}\n"
        f"Sessão #{g['session']} começou com {len(g['players'])} jogador(es).",
    )
    await refresh_panel(interaction.guild_id)


@treino.command(name="remover", description="Remove um jogador do treino")
@app_commands.describe(membro="Jogador a remover")
async def cmd_remove(interaction: discord.Interaction, membro: discord.Member):
    g = store.guild(interaction.guild_id)
    if g["players"].pop(str(membro.id), None) is None:
        await reply(interaction, f"{membro.mention} não está no treino.")
        return
    store.save()
    await reply(interaction, f"{membro.mention} removido do treino.")
    await refresh_panel(interaction.guild_id)


@treino.command(name="limpar", description="Remove todos os jogadores do treino")
async def cmd_clear(interaction: discord.Interaction):
    g = store.guild(interaction.guild_id)
    count = len(g["players"])
    g["players"].clear()
    store.save()
    await reply(interaction, f"Treino limpo. {count} jogador(es) removido(s).")
    await refresh_panel(interaction.guild_id)


class TrainingBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(treino)

    async def setup_hook(self):
        self.add_view(TrainingView())
        if GUILD_ID:
            guild = discord.Object(int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        print(f"Logado como {self.user} (id {self.user.id})")


bot = TrainingBot()

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Defina DISCORD_TOKEN no arquivo .env (veja .env.example).")
    bot.run(TOKEN)
