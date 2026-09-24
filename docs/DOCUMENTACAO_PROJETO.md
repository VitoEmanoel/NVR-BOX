# Documentacao do Projeto NVRBox

## Visao geral

O NVRBox e um sistema NVR residencial simples para uso local. Ele foi criado para centralizar cameras IP com stream RTSP, gravar os videos em armazenamento local ou externo e disponibilizar um painel web para acompanhar o estado das cameras, ver o ao vivo, consultar gravacoes, reproduzir trechos salvos e baixar arquivos.

A proposta do projeto e entregar uma solucao leve, direta e executavel em uma maquina comum da rede local, como PC Linux, mini PC, notebook, TV Box compativel com Python/FFmpeg ou ambiente semelhante. O foco do sistema e operacao local: a maquina roda os processos de painel, captura e limpeza, enquanto as cameras fornecem os streams RTSP pela rede.

## O que o sistema entrega hoje

O sistema entrega um painel web em Flask com cadastro, visualizacao, gravacao e manutencao basica das cameras.

As principais entregas atuais sao:

- Painel web para gerenciamento das cameras.
- Cadastro simplificado por nome, IP, senha e perfil RTSP.
- Campos avancados para usuario, porta RTSP, MAC, protocolo UDP/TCP e caminho RTSP manual.
- Edicao de cameras pela tela de detalhe.
- Preservacao do slug da camera durante edicoes, mantendo as gravacoes antigas associadas.
- Teste real de stream RTSP com `ffprobe` antes de salvar novas cameras e edicoes que alteram a conexao.
- Listagem de cameras cadastradas.
- Indicacao de cameras online e offline.
- Live view individual via MJPEG.
- Gravacao continua usando FFmpeg.
- Segmentacao das gravacoes em arquivos `.mp4`.
- Segmentos MP4 fragmentados para melhorar a reproducao de arquivos gerados em paradas curtas ou interrupcoes.
- Historico de gravacoes por camera.
- Calendario interativo por camera com contador de gravacoes por dia.
- Filtro de gravacoes por data.
- Lista de gravacoes por dia, sem abrir os arquivos, com duracao estimada e indicacao do segmento em gravacao.
- Separacao visual entre gravacoes reproduziveis e arquivos incompletos ou invalidos.
- Reproducao de gravacoes no painel.
- Rota compativel com navegador para gerar WebM sob demanda quando necessario.
- Download do arquivo `.mp4` original.
- Acoes explicitas de player e download na lista de gravacoes.
- Escolha do armazenamento de gravacao pelo painel.
- Deteccao de memorias gravaveis em caminhos comuns de Linux, TV Box e Android.
- Limpeza automatica de gravacoes antigas quando o uso do disco passa do limite configurado.
- Remocao de cameras por requisicao `POST`.
- Mascaramento de senha RTSP na interface.
- Autenticacao HTTP basica opcional por variaveis de ambiente.
- Escrita atomica dos arquivos JSON usados pelo sistema.
- Slugs seguros para rotas, nomes de arquivos e logs.
- Rotacao simples dos logs do FFmpeg.
- Script de inicializacao para subir painel, captura e limpeza.

## Fluxo de funcionamento

O NVRBox funciona com tres processos principais e um modulo compartilhado de configuracao.

1. `servidor.py` inicia o painel web em Flask.
2. `captura.py` executa o motor de captura continua.
3. `limpeza.py` acompanha o uso do armazenamento e remove gravacoes antigas quando necessario.
4. `config.py` centraliza configuracoes, caminhos, perfis RTSP, armazenamento, slugs, leitura e escrita de JSON.

O fluxo operacional e:

1. O usuario acessa o painel pelo navegador.
2. O painel carrega as cameras salvas em `cameras.local.json`.
3. O painel mostra estado online/offline, quantidade de gravacoes e uso de disco.
4. O usuario cadastra ou edita cameras informando IP, senha, perfil RTSP e campos opcionais.
5. O backend monta a URL RTSP a partir dos dados informados.
6. O sistema testa o stream RTSP com `ffprobe`.
7. O processo `captura.py` le as cameras cadastradas.
8. Para cada camera, o sistema inicia um processo FFmpeg.
9. O FFmpeg grava arquivos `.mp4` segmentados na pasta de gravacoes ativa.
10. A tela de detalhe abre o ao vivo via MJPEG.
11. A tela de detalhe lista gravacoes da camera e permite reproduzir ou baixar arquivos.
12. A rotina `limpeza.py` verifica periodicamente o uso do disco e remove videos antigos elegiveis quando o limite configurado e ultrapassado.

Quando o armazenamento ativo muda, o motor de captura reinicia os processos FFmpeg para gravar no novo caminho. Quando a URL RTSP ou o protocolo de uma camera muda por edicao, o motor de captura reinicia a captura daquela camera no proximo ciclo do watchdog.

## Interface web

O painel principal apresenta uma visao geral do sistema:

- Uso do HD.
- Armazenamento selecionado.
- Total de cameras online.
- Total de cameras offline.
- Formulario de cadastro de nova camera.
- Cards das cameras cadastradas.
- Quantidade de gravacoes por camera.
- Estado RTSP de cada camera.
- Acesso para abrir a camera individual.
- Remocao de camera cadastrada.

A tela de detalhe da camera apresenta:

- Nome da camera.
- URL RTSP mascarada.
- Botao de edicao com icone de lapis.
- Live view individual.
- Botao para voltar ao ao vivo depois de abrir uma gravacao.
- Lista de gravacoes.
- Calendario de gravacoes com destaque para dias com videos salvos.
- Filtro por data.
- Acao `Player` para reproduzir uma gravacao.
- Acao `Download` para baixar o `.mp4` original.
- Indicacao de gravacoes validas.
- Estado online/offline da camera.

## Cameras e perfis RTSP

O sistema trabalha com cameras IP que disponibilizam stream RTSP. O cadastro simplificado recebe:

- Nome da camera.
- IP da camera.
- Senha da camera.
- Perfil RTSP.

Os campos avancados permitem configurar:

- Usuario da camera.
- Porta RTSP.
- MAC.
- Protocolo RTSP (`udp` ou `tcp`).
- Caminho RTSP manual.

Os perfis RTSP conhecidos ficam em `config.py`, no dicionario `RTSP_PERFIS`. O sistema inclui perfis para:

- ONVIF / Intelbras.
- Hikvision.
- Dahua.
- XM / Yoosee.
- Generica CH00.
- Caminho manual informado pelo usuario.

Ao salvar uma camera, o backend gera a URL RTSP usando os dados informados. A interface exibe a URL com senha mascarada.

## Gravacao

A captura usa FFmpeg para consumir o RTSP de cada camera e gravar arquivos de video.

Cada camera cadastrada recebe um processo FFmpeg proprio. O nome dos arquivos usa o slug da camera e a data/hora de inicio do segmento:

```text
camera_slug_YYYY-MM-DD_HH-MM-SS.mp4
```

Por padrao, cada segmento tem duracao alvo de 600 segundos, ou 10 minutos. O painel permite escolher segmentos de 5, 10 ou 15 minutos. Esse valor tambem pode ser alterado pela variavel de ambiente `NVRBOX_TEMPO_SEGMENTO`, que tem prioridade sobre a escolha salva no painel.

O FFmpeg usa:

- `-rtsp_transport` com `udp` ou `tcp`;
- timeout de rede (`-timeout`, ou `-stimeout` em FFmpeg antigo), para desistir de uma camera que para de enviar dados;
- `-nostats -loglevel warning`, para registrar so avisos e erros;
- copia do video com `-c:v copy`;
- audio em AAC com `-c:a aac`;
- formato segmentado;
- MP4 fragmentado com `frag_keyframe`, `empty_moov` e `default_base_moof`;
- nomes com data/hora via `strftime`.

Os logs de erro do FFmpeg ficam no mesmo armazenamento das gravacoes com nome baseado no slug da camera:

```text
erro_camera_slug.txt
```

O log e aberto em modo de acrescimo, com uma linha `=== data hora Iniciando captura ===` a cada inicio, entao o erro que derrubou a gravacao anterior fica preservado. Quando passa de `NVRBOX_FFMPEG_LOG_MAX_BYTES`, o conteudo e copiado para `erro_camera_slug.txt.1` e o original e zerado, mesmo com o FFmpeg rodando.

### Vigia da gravacao

A cada 10 segundos, `captura.py` confere se o segmento que cada FFmpeg esta escrevendo continua crescendo. O arquivo aberto e lido em `/proc/<pid>/fd`; sem `/proc`, usa o segmento mais recente da camera pelo nome.

- Se o FFmpeg encerrar, ele e reiniciado, respeitando um intervalo minimo de 30 segundos entre tentativas.
- Se o arquivo ficar sem crescer por `NVRBOX_LIMITE_SEM_GRAVACAO` segundos (padrao 60), a gravacao e considerada travada e o FFmpeg e reiniciado, mesmo com o processo vivo e a conexao aberta.
- Se nenhum video for gravado em 90 segundos apos iniciar, o FFmpeg tambem e reiniciado.

A comparacao usa relogio monotonico, entao ajustes de horario (comuns em placas sem RTC apos queda de energia) nao disparam reinicios falsos.

### Estado da gravacao no painel

`captura.py` salva o estado de cada camera em `.run/estado_captura.json` (ou `NVRBOX_ESTADO_CAPTURA`): gravando, conectando ou parada, horario da ultima gravacao, numero de reinicios, ultimo motivo e ultima linha do log (com senha mascarada). O arquivo e regravado quando algo muda e, no maximo, a cada 60 segundos, sem `fsync`, para poupar cartao SD.

O painel inicial e a tela da camera leem esse arquivo:

- `Gravando`: o segmento cresceu recentemente.
- `Conectando...`: a captura esta tentando conectar ou reconectar.
- `Sem gravar ha X`: nada gravado ha mais de 2 minutos; a tela da camera mostra o ultimo erro.
- `Motor de gravacao parado`: o arquivo nao existe, esta desatualizado ha mais de 3 minutos ou a captura foi encerrada. O painel inicial mostra um aviso geral de que nenhuma camera esta gravando.

O status "online" continua sendo apenas o teste da porta RTSP e nao indica que a camera esta gravando.

## Identificacao das cameras pelo MAC

Quando falta energia ou o roteador reinicia, as cameras podem receber IPs diferentes, inclusive trocados entre si. O MAC de cada camera nao muda, entao o sistema usa o MAC para saber qual aparelho e qual camera. Isso fica em `rede.py`.

- No cadastro e na edicao, o MAC e preenchido sozinho a partir da tabela ARP depois do teste da camera. O usuario nao precisa digitar.
- Cameras antigas sem MAC aprendem o MAC automaticamente na primeira vez que estiverem gravando.
- Antes de iniciar cada gravacao, `captura.py` confere se o IP salvo ainda pertence ao MAC da camera. Se nao pertencer, procura o MAC na tabela ARP e, se preciso, varre a rede local (/24 do ultimo IP, porta RTSP, cerca de 7 segundos). Achando, atualiza IP e URL RTSP em `cameras.local.json` e registra "Camera mudou de endereco (... -> ...) e o sistema atualizou sozinho".
- A conferencia roda para toda camera que nao esta gravando a cada 30 segundos, antes da checagem do HD. Assim, mesmo com o HD desconectado e a gravacao parada, o cadastro acompanha a troca de IP e o ao vivo do painel nunca mostra a camera errada.
- A cada ciclo de 10 segundos, a captura tambem confere se o IP de uma camera que esta gravando passou a ser de outro aparelho. Se passou, reinicia a camera, que e procurada de novo.
- Camera nao encontrada aparece no painel como "Camera nao encontrada na rede". O sistema continua tentando a cada 30 segundos e varre a rede no maximo a cada 5 minutos por camera.
- Ao mudar o IP de uma camera pela edicao, o MAC antigo e descartado e aprendido de novo no IP novo. Sem isso, a captura "corrigiria" o IP de volta.
- Um MAC ja usado por outra camera nao e salvo, para nao confundir cameras atras de repetidores Wi-Fi que mostram o mesmo MAC para varios aparelhos.

Limitacoes: funciona com o NVR na mesma rede local das cameras. No Android 10+ (Termux) a tabela ARP e bloqueada; nesse caso o sistema segue usando o IP salvo, sem bloquear a gravacao.

## Reproducao e download

As gravacoes ficam listadas na tela de detalhe de cada camera, um dia por vez. A tela abre no dia mais recente com gravacao; o calendario troca o dia.

A lista nao abre os arquivos. No Orange Pi, um `ffprobe` levava ~4 segundos por segmento e a lista de um dia demorava minutos; agora ela sai em milissegundos:

- a duracao e estimada pelo horario de inicio (no nome do arquivo) e pela ultima modificacao do arquivo;
- o segmento mais novo da camera, modificado no ultimo minuto, aparece como "Gravando agora";
- arquivos com menos de 64 KB que nao estao gravando aparecem como invalidos.

Se o navegador nao conseguir tocar o `.mp4` original, o player tenta sozinho a rota compativel abaixo.

Ao clicar em `Player`, o painel interrompe o live view da tela, mostra o player de video e carrega uma rota compativel:

```text
/video_compativel/<arquivo>
```

Essa rota usa FFmpeg para entregar WebM sob demanda ao navegador. O arquivo original permanece preservado.

Ao clicar em `Download`, o sistema entrega o `.mp4` original:

```text
/download/<arquivo>
```

## Armazenamento

O caminho de gravacao e resolvido em `config.py`. A ordem usada pelo sistema e:

1. Variavel de ambiente `NVRBOX_GRAVACOES`.
2. Caminho salvo em `sistema.json`.
3. Memorias gravaveis detectadas em caminhos comuns.
4. Pasta local `gravacoes/`.

O painel principal permite escolher o armazenamento de gravacao. A escolha fica salva em `sistema.json`.

O sistema procura memorias em caminhos comuns de Linux, TV Box e Android:

- `/media`
- `/mnt`
- `/storage`
- `/run/media`
- `/sdcard`
- `/storage/emulated/0`
- `/storage/self/primary`

Antes de usar uma pasta, o sistema testa permissao de escrita criando e removendo um arquivo temporario.

Em memorias externas (dentro de `/media`, `/mnt`, `/storage` ou `/run/media`), o disco precisa estar montado dentro dessa raiz. Se o HD estiver desconectado, o sistema nao cria a pasta (o que faria a gravacao ir para o disco do sistema sem aviso) e trata o armazenamento como indisponivel:

- o painel continua abrindo e mostra "Nao e possivel gravar" com o motivo;
- `captura.py` para os FFmpeg, registra o motivo uma vez e volta sozinha quando o HD reaparece;
- `limpeza.py` suspende a limpeza ate o HD voltar;
- a camera aparece como "Sem gravar" com o motivo na tela de detalhe.

Um caminho salvo que ficou indisponivel nao e trocado automaticamente por outro: o sistema avisa em vez de gravar em outro lugar. A captura confere a montagem a cada ciclo e testa escrita a cada 60 segundos.

## Limpeza automatica

O processo `limpeza.py` acompanha o uso do armazenamento ativo. O limite padrao e 90% de uso do disco, definido por `NVRBOX_LIMITE_DISCO`.

Quando o uso passa do limite configurado, o sistema remove arquivos `.mp4` antigos elegiveis ate o armazenamento voltar ao limite. A limpeza ignora arquivos modificados recentemente para evitar remover segmentos em uso.

## Configuracoes locais

O sistema usa arquivos locais para guardar estado e configuracao da maquina.

`cameras.local.json` guarda as cameras cadastradas. Esse arquivo contem dados reais de conexao e fica fora do Git.

`cameras.example.json` e um modelo versionado sem credenciais reais.

`sistema.json` guarda configuracoes locais do sistema, como o caminho de videos escolhido pelo painel.

`gravacoes/` e a pasta local usada como fallback de armazenamento.

`.run/` guarda arquivos PID usados pelo script de inicializacao.

## Variaveis de ambiente

O sistema aceita variaveis de ambiente para ajustar comportamento sem alterar codigo:

- `NVRBOX_AUTH_USUARIO`: usuario da autenticacao HTTP basica.
- `NVRBOX_AUTH_SENHA`: senha da autenticacao HTTP basica.
- `NVRBOX_GRAVACOES`: caminho fixo para gravacoes.
- `NVRBOX_CAMERAS`: caminho alternativo para o JSON de cameras.
- `NVRBOX_LIMITE_DISCO`: limite de uso do disco para limpeza automatica, padrao `90`.
- `NVRBOX_TEMPO_SEGMENTO`: duracao alvo de cada segmento em segundos, padrao `600`.
- `NVRBOX_RTSP_TRANSPORTE`: transporte RTSP padrao, `udp` ou `tcp`, padrao `udp`.
- `NVRBOX_TESTAR_RTSP_CADASTRO`: liga ou desliga o teste RTSP no cadastro e edicao, padrao `1`.
- `NVRBOX_TIMEOUT_TESTE_RTSP`: tempo maximo do teste RTSP em segundos, padrao `20`.
- `NVRBOX_FFMPEG_LOG_MAX_BYTES`: tamanho maximo do log FFmpeg antes da rotacao, padrao `2097152`.
- `NVRBOX_TIMEOUT_RTSP`: segundos sem dados da camera ate o FFmpeg desistir da conexao (captura e live view), padrao `15`, maximo `2000`.
- `NVRBOX_LIMITE_SEM_GRAVACAO`: segundos com o segmento sem crescer ate a captura considerar a gravacao travada e reiniciar, padrao `60`.
- `NVRBOX_ESTADO_CAPTURA`: caminho do arquivo de estado da captura, padrao `.run/estado_captura.json`.

Exemplo de autenticacao HTTP basica:

```bash
export NVRBOX_AUTH_USUARIO="admin"
export NVRBOX_AUTH_SENHA="troque-esta-senha"
```

## Tecnologias usadas

O NVRBox usa as seguintes tecnologias:

- Python 3 como linguagem principal.
- Flask como framework web.
- Jinja2 nos templates HTML renderizados pelo Flask.
- HTML, CSS e JavaScript no painel.
- Phosphor Icons via CDN para icones da interface.
- FFmpeg para captura RTSP, segmentacao MP4, live MJPEG e conversao WebM sob demanda.
- ffprobe para testar streams RTSP no cadastro.
- RTSP como protocolo de video das cameras.
- MJPEG para live view no navegador.
- MP4 fragmentado para armazenamento das gravacoes.
- WebM como formato compativel gerado sob demanda para reproducao no navegador.
- JSON para configuracao local de cameras e sistema.
- Bash no script `iniciar_nvr.sh`.
- Git para versionamento do codigo.

## Requisitos para rodar

Para o sistema funcionar, o ambiente precisa ter:

- Python 3 instalado.
- Flask instalado pelas dependencias do projeto.
- FFmpeg instalado no sistema.
- ffprobe disponivel junto com o FFmpeg.
- Bash para executar `iniciar_nvr.sh`.
- Acesso de rede entre a maquina do NVRBox e as cameras.
- Cameras IP com RTSP habilitado.
- Credenciais corretas das cameras.
- Permissao de escrita na pasta de gravacoes.
- Navegador moderno para acessar o painel web.

As dependencias Python ficam em `requirements.txt`:

```text
Flask>=3.0,<4.0
```

Instalacao das dependencias Python:

```bash
pip install -r requirements.txt
```

## Como executar

Para iniciar os tres processos principais com o script do projeto:

```bash
./iniciar_nvr.sh
```

O script inicia:

1. `limpeza.py`
2. `captura.py`
3. `servidor.py`

Tambem e possivel executar os processos separadamente:

```bash
python3 limpeza.py
python3 captura.py
python3 servidor.py
```

Depois de iniciar o painel, o acesso local e:

```text
http://127.0.0.1:5000
```

Em outro dispositivo da mesma rede, use o IP da maquina onde o NVRBox esta rodando:

```text
http://IP_DA_MAQUINA:5000
```

## Arquivos principais

- `servidor.py`: painel Flask, rotas, validacoes, live view, reproducao e download.
- `captura.py`: motor de captura FFmpeg e watchdog das cameras.
- `limpeza.py`: limpeza automatica por uso de disco.
- `config.py`: configuracoes compartilhadas, armazenamento, perfis RTSP, JSON e slugs.
- `templates/index.html`: tela principal do painel.
- `templates/detalhe.html`: tela individual da camera.
- `static/css/index.css`: estilos da tela principal.
- `static/css/detalhe.css`: estilos da tela individual.
- `iniciar_nvr.sh`: script de inicializacao dos processos.
- `requirements.txt`: dependencias Python.
- `cameras.example.json`: exemplo de configuracao de cameras.
- `README.md`: guia principal do repositorio.

## Verificacoes do projeto

Os comandos usados para validar sintaxe e configuracao basica sao:

```bash
python3 -m py_compile servidor.py captura.py limpeza.py config.py
python3 -m json.tool cameras.example.json
test ! -f cameras.local.json || python3 -m json.tool cameras.local.json
bash -n iniciar_nvr.sh
```

Essas verificacoes confirmam sintaxe Python, validade do JSON de exemplo, validade do JSON local quando existir e sintaxe do script shell.
