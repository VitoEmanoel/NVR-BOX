# Analise do Projeto NVRBox

## Visao geral

O NVRBox e um prototipo de NVR residencial com arquitetura simples e funcional. O sistema usa Flask para o painel web, FFmpeg para captura RTSP e arquivos `.mp4` segmentados para armazenar as gravacoes.

A proposta atual e adequada para uso local, estudo e demonstracao de TCC. Antes de uso continuo em ambiente real, o projeto ainda precisa de melhorias em seguranca, controle de processos, padronizacao de caminhos e tratamento de erros. As tarefas acionaveis ficam centralizadas em `docs/ROADMAP.md`.

## Arquitetura atual

O projeto esta dividido em tres processos principais:

- `servidor.py`: painel web em Flask.
- `captura.py`: captura continua usando FFmpeg.
- `limpeza.py`: limpeza automatica dos videos antigos.

Arquivos e pastas de apoio:

- `cameras.json`: configuracao das cameras.
- `iniciar_nvr.sh`: inicializacao manual dos processos.
- `templates/`: HTML das telas renderizadas pelo Flask.
- `static/css/`: CSS separado dos templates.
- `docs/`: documentacao tecnica e roadmap.

Fluxo principal:

1. `captura.py` le `cameras.json`.
2. Para cada camera configurada, inicia um processo `ffmpeg`.
3. O FFmpeg grava segmentos `.mp4` na pasta de gravacoes.
4. `servidor.py` lista cameras, status e arquivos gravados.
5. `limpeza.py` monitora o uso do armazenamento e remove videos antigos quando necessario.

## Estado atual

O projeto ja entrega as funcoes centrais de um painel NVR simples:

- cadastro de cameras;
- listagem de cameras;
- status online/offline;
- live view via MJPEG;
- historico de gravacoes;
- filtro por data;
- download de videos;
- limpeza automatica de gravacoes antigas.

A interface tambem ja foi organizada em HTML e CSS separados:

- `templates/index.html` usa `static/css/index.css`;
- `templates/detalhe.html` usa `static/css/detalhe.css`.

## Pontos fortes

- A separacao entre painel, captura e limpeza deixa as responsabilidades claras.
- FFmpeg e uma escolha adequada para RTSP, gravacao e segmentacao de video.
- A segmentacao em arquivos de 10 minutos facilita navegacao, download e limpeza.
- O codigo ainda e pequeno e facil de entender.
- A configuracao em JSON simplifica o prototipo e facilita edicao manual.
- A interface cobre as operacoes principais do sistema.

## Pontos de atencao

### Seguranca

O painel nao possui login por decisao de projeto. Essa escolha e aceitavel somente se o acesso ficar restrito a `localhost` ou Tailscale.

O sistema nao deve ser publicado em:

- IP publico;
- dominio publico;
- rede Wi-Fi de terceiros;
- porta aberta no roteador;
- proxy reverso publico sem autenticacao.

Mesmo em rede privada, ainda e importante mascarar URLs RTSP na interface e evitar que usuario e senha aparecam em tela ou logs.

### Controle de processos

O projeto ainda usa encerramentos amplos, como `pkill`, em alguns pontos. Isso pode afetar processos que nao pertencem ao NVRBox. O ideal e controlar PIDs iniciados pelo proprio sistema e encerrar apenas o processo relacionado a camera ou rotina correta.

Tambem e necessario garantir que `captura.py` encerre o FFmpeg de uma camera removida do `cameras.json`.

### Caminhos de gravacao

Ha risco de painel, captura e limpeza usarem pastas diferentes dependendo do diretorio de execucao e da deteccao de armazenamento. O caminho de gravacoes deve ser resolvido de forma unica e reutilizado pelos tres processos.

### Dados e validacao

O cadastro de cameras ainda precisa de validacoes mais fortes. Nome, slug, MAC e URL RTSP devem ser verificados antes de salvar no JSON.

O campo `protocolo` aparece no formulario, mas ainda precisa ser salvo e usado pelo backend ou removido da interface.

### Tratamento de erros

Existem pontos com `except:` generico. Isso evita quedas em alguns cenarios, mas tambem esconde falhas reais. O ideal e capturar excecoes especificas e registrar mensagens claras.

## Operacao

Hoje o sistema pode ser executado manualmente com processos separados:

```bash
python3 limpeza.py
python3 captura.py
python3 servidor.py
```

Para uso mais confiavel, o projeto deve evoluir para gerenciamento por `systemd` ou mecanismo equivalente, com restart automatico, logs separados e permissoes bem definidas.

## Verificacoes basicas

Comandos uteis para validar alteracoes:

```bash
python3 -m py_compile servidor.py captura.py limpeza.py
python3 -m json.tool cameras.json
bash -n iniciar_nvr.sh
```

Essas verificacoes cobrem sintaxe Python, validade do JSON e sintaxe do script shell. Elas nao substituem testes funcionais com cameras reais, gravacao em disco, reproducao pelo painel e limpeza automatica.

## Conclusao

O NVRBox tem uma base tecnica coerente para um prototipo residencial: Flask resolve bem o painel, FFmpeg resolve a captura RTSP e a separacao dos processos facilita entender o sistema.

O foco das proximas evolucoes deve ser confiabilidade operacional e seguranca contextual: caminhos consistentes, controle correto de processos, remocao segura de cameras, mascaramento de credenciais e validacao de entradas. O acompanhamento dessas tarefas deve ser feito em `docs/ROADMAP.md`.
