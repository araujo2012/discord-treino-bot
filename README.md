# Bot de Sessão de Treino

Painel com botões num canal do Discord para gerenciar jogadores de uma sessão de treino.
Toda resposta aos jogadores é efêmera (só quem clicou vê).

## Botões

| Botão | O que faz |
|---|---|
| **Treinar** | Entra no treino. Se tinha marcado Ausentar, cancela a ausência. |
| **Sair** | Sai do treino na hora. |
| **Ausentar** | Marca para sair no fim da sessão atual. Clicar de novo cancela. |
| **Status** | Lista quem está no treino (e quem sai no fim da sessão). |

## Comandos de admin (`/treino`)

Só aparecem para quem tem a permissão **Gerenciar Servidor** (dá pra mudar em Configurações do servidor → Integrações).

| Comando | O que faz |
|---|---|
| `/treino painel` | Publica o painel no canal atual (apaga o painel anterior, se houver). |
| `/treino encerrar` | Encerra a sessão: remove quem marcou Ausentar e começa a próxima sessão. |
| `/treino remover @membro` | Tira um jogador do treino. |
| `/treino limpar` | Tira todo mundo do treino. |

## Setup

1. **Criar o bot**: https://discord.com/developers/applications → *New Application* → aba **Bot** → *Reset Token* e copie o token.
2. **Convidar pro servidor**: aba **OAuth2 → URL Generator** → marque os scopes `bot` e `applications.commands`; em permissões marque `View Channels`, `Send Messages`, `Embed Links`, `Manage Messages`. Abra a URL gerada e escolha o servidor.
3. **Configurar**: copie `.env.example` para `.env` e cole o token em `DISCORD_TOKEN`.
   Opcional: coloque o ID do servidor em `GUILD_ID` (clique direito no servidor → *Copiar ID*, precisa do Modo Desenvolvedor ativo) para os comandos aparecerem na hora. Sem isso, os comandos globais podem levar alguns minutos para aparecer.
4. **Rodar**:
   ```bash
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   .venv\Scripts\python bot.py
   ```
5. No canal desejado, rode `/treino painel`.

O estado (jogadores, sessão atual, painel) fica em `data.json`, então reiniciar o bot não perde nada e os botões continuam funcionando.
O bot só fica online enquanto o `bot.py` está rodando. Pra deixar 24/7, rode numa VPS (abaixo).

## Deploy em VPS (Linux com systemd)

Roteiro para Ubuntu/Debian. Rode como root (ou com `sudo`):

```bash
apt update && apt install -y python3 python3-venv git
useradd --system --create-home --shell /usr/sbin/nologin treinobot
git clone https://github.com/araujo2012/discord-treino-bot.git /opt/treino-bot
cd /opt/treino-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env   # cole o DISCORD_TOKEN
chown -R treinobot:treinobot /opt/treino-bot
chmod 600 .env
cp deploy/treino-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now treino-bot
```

Comandos úteis:

```bash
systemctl status treino-bot        # está rodando?
journalctl -u treino-bot -f        # logs ao vivo
```

Atualizar para a versão mais nova do repositório:

```bash
cd /opt/treino-bot
sudo -u treinobot git pull
sudo -u treinobot .venv/bin/pip install -r requirements.txt
systemctl restart treino-bot
```

O `systemd` reinicia o bot sozinho se ele cair ou se a VPS reiniciar.
