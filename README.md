# NVR-BOX

NVRBox e um NVR residencial simples para uso local. Ele usa Flask para o painel web, FFmpeg para capturar cameras RTSP e arquivos `.mp4` segmentados e fragmentados para armazenar as gravacoes.

O uso previsto e em `localhost`, rede local confiavel ou Tailscale. Por padrao, o painel continua sem login para manter o uso local simples; existe autenticacao opcional por variaveis de ambiente. O sistema nao deve ser exposto em IP publico, dominio publico ou porta aberta no roteador sem autenticacao e protecao de rede.

Se precisar colocar o painel em uma rede onde outras pessoas tenham acesso, ative a autenticacao HTTP basica com variaveis de ambiente:

```bash
export NVRBOX_AUTH_USUARIO="admin"
export NVRBOX_AUTH_SENHA="troque-esta-senha"
```

Sem essas duas variaveis, o painel continua sem login para manter o uso local simples.

## Funcionalidades atuais

- Painel web em Flask.
- Cadastro simplificado de cameras por nome, IP, senha e perfil RTSP.
- Perfis RTSP conhecidos para ONVIF/Intelbras, Hikvision, Dahua, XM/Yoosee e generico.
- Modo avancado para usuario, porta, MAC, protocolo UDP/TCP e caminho RTSP manual.
- Live view via MJPEG.
- Gravacao por FFmpeg em segmentos `.mp4`.
- Segmentos `.mp4` fragmentados para preservar reproducao mesmo em paradas antes dos 10 minutos.
- Historico de gravacoes por camera.
- Filtro por data.
- Reproducao de gravacoes no proprio painel.
- Rota de reproducao compativel com navegador usando FFmpeg/WebM quando o `.mp4` original nao toca diretamente.
- Download de videos.
- Remocao de cameras por `POST`.
- Mascaramento de senha RTSP na interface.
- Escolha da memoria de gravacao pelo painel.
- Limpeza automatica quando o disco passa do limite configurado.
- Configuracao real de cameras em arquivo local ignorado pelo Git.
- Slugs seguros para rotas, nomes de arquivos e logs.
- Mensagens de erro e sucesso exibidas no painel.
- Teste real de stream RTSP antes de salvar uma nova camera.
- Autenticacao opcional por variaveis de ambiente.
- Rotacao simples dos logs do FFmpeg.

## Requisitos

- Python 3.
- FFmpeg instalado no sistema.
- Flask.

Instale as dependencias Python:

```bash
pip install -r requirements.txt
```

## Execucao

Para iniciar o sistema completo:

```bash
./iniciar_nvr.sh
```

Ou rode os processos separadamente:

```bash
python3 limpeza.py
python3 captura.py
python3 servidor.py
```

Depois acesse:

```text
http://127.0.0.1:5000
```

Em outro dispositivo da rede ou via Tailscale, use o IP da maquina onde o servidor esta rodando.

## Armazenamento

O usuario pode escolher a memoria de gravacao no painel principal. A escolha fica salva em `sistema.json`, que e um arquivo local da maquina e nao deve ser versionado.

A ordem de resolucao do armazenamento e:

1. Variavel de ambiente `NVRBOX_GRAVACOES`, se existir.
2. Caminho salvo em `sistema.json`.
3. Memorias gravaveis detectadas em caminhos comuns de Linux, TV Box e Android.
4. Fallback local em `gravacoes/`.

Ao trocar a memoria pelo painel, a captura reinicia os processos FFmpeg para gravar no novo caminho. As gravacoes antigas permanecem na memoria anterior.

## Ao vivo e gravacoes

O painel principal mostra as cameras cadastradas, o status online/offline e a quantidade de gravacoes por camera. Para ver o video ao vivo, abra a camera pelo botao `Abrir Camera`; o stream MJPEG e carregado na tela de detalhe.

Na tela da camera, a lista `Gravacoes` mostra os arquivos encontrados no armazenamento ativo. Use o filtro de data para buscar um dia especifico e clique em uma gravacao valida para reproduzir no player. Ao abrir uma gravacao, o painel interrompe o stream ao vivo, mostra o player de video e usa uma rota compativel com navegador (`/video_compativel/<arquivo>`) para converter o trecho sob demanda para WebM quando necessario. O download continua entregando o arquivo `.mp4` original.

Arquivos antigos ou interrompidos antes desta versao podem aparecer como incompletos se nao puderem ser lidos pelo `ffprobe`.

## Gravacoes curtas e queda de energia

Cada segmento tem duracao alvo de 10 minutos por padrao. Se a energia cair, o processo for encerrado ou a camera parar antes disso, o trecho ja gravado deve continuar reproduzivel. Para isso, a captura usa MP4 fragmentado (`frag_keyframe`, `empty_moov` e `default_base_moof`), que escreve metadados no inicio e ao longo do arquivo em vez de depender apenas do fechamento final.

Arquivos antigos gravados antes dessa configuracao podem continuar aparecendo como incompletos se perderam o indice final do MP4.

## Configuracao de cameras

O cadastro principal pede:

- nome da camera;
- IP da camera;
- senha;
- perfil/modelo RTSP.

As opcoes avancadas permitem ajustar:

- usuario, padrao `admin`;
- porta RTSP, padrao `554`;
- MAC;
- protocolo UDP/TCP;
- caminho RTSP manual.

As cameras ficam salvas em `cameras.local.json`, que e um arquivo local da maquina e nao deve ser versionado. O repositorio mantem `cameras.example.json` apenas como modelo sem credenciais reais.

Para criar uma configuracao inicial manualmente, copie o exemplo e ajuste os dados:

```bash
cp cameras.example.json cameras.local.json
```

Por padrao, o sistema testa o stream RTSP com `ffprobe` antes de salvar uma nova camera. Para ambientes onde a camera so fica acessivel depois de ajustes externos, esse teste pode ser desligado:

```bash
export NVRBOX_TESTAR_RTSP_CADASTRO=0
```

## Variaveis de ambiente uteis

- `NVRBOX_AUTH_USUARIO` e `NVRBOX_AUTH_SENHA`: ativam autenticacao HTTP basica.
- `NVRBOX_GRAVACOES`: forca o caminho de gravacao.
- `NVRBOX_CAMERAS`: muda o arquivo JSON de cameras.
- `NVRBOX_LIMITE_DISCO`: limite de uso do disco para limpeza automatica, padrao `90`.
- `NVRBOX_TEMPO_SEGMENTO`: duracao de cada segmento em segundos, padrao `600`.
- `NVRBOX_RTSP_TRANSPORTE`: transporte padrao `udp` ou `tcp`, padrao `udp`.
- `NVRBOX_TESTAR_RTSP_CADASTRO`: liga/desliga o teste RTSP no cadastro, padrao `1`.
- `NVRBOX_TIMEOUT_TESTE_RTSP`: tempo maximo do teste RTSP em segundos, padrao `8`.
- `NVRBOX_FFMPEG_LOG_MAX_BYTES`: tamanho maximo de cada log FFmpeg antes da rotacao, padrao `2097152`.

## Verificacoes

Antes de considerar uma alteracao concluida, rode:

```bash
python3 -m py_compile servidor.py captura.py limpeza.py config.py
python3 -m json.tool cameras.example.json
test ! -f cameras.local.json || python3 -m json.tool cameras.local.json
bash -n iniciar_nvr.sh
```

## Proximas melhorias

As tarefas pendentes ficam em `docs/ROADMAP.md`. Os proximos pontos principais sao tratar melhor erros de JSON local, validar armazenamento em Android/TV Box e preparar execucao por servico.
