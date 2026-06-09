# Roadmap do Projeto NVRBox

Este arquivo e o backlog unico do projeto. Quando uma tarefa for concluida, remova ou atualize a entrada correspondente para evitar informacao duplicada ou desatualizada.

## Prioridade alta

- Corrigir o caminho do script de limpeza em `iniciar_nvr.sh`.
  - Atual: `python3 ../limpeza.py`
  - Esperado: `python3 limpeza.py`

- Unificar o caminho de gravacoes entre `servidor.py`, `captura.py` e `limpeza.py`.
  - O painel, a captura e a limpeza devem ler e escrever na mesma pasta.
  - Evite caminhos relativos dependentes do diretorio de execucao.

- Remover comandos de encerramento muito amplos.
  - `iniciar_nvr.sh` usa `pkill -f ffmpeg`, que pode encerrar FFmpeg fora do NVRBox.
  - `servidor.py` usa `pkill -9 -f image2pipe`, que pode derrubar streams ativos de outras cameras.
  - O ideal e encerrar processos pelo PID controlado pelo proprio sistema.

- Trocar a remocao de cameras de `GET` para `POST`.
  - A rota atual `/apagar_camera/<nome>` altera estado por link simples.
  - O HTML deve usar formulario com `method="POST"`.

- Mascarar a URL RTSP na interface.
  - `templates/detalhe.html` ainda exibe a URL completa.
  - A senha nao deve aparecer no painel.

- Garantir que a remocao de uma camera encerre o FFmpeg correspondente.
  - `captura.py` deve comparar cameras ativas com `cameras.json`.
  - Processos sem camera correspondente devem ser finalizados e removidos do controle interno.

## Prioridade media

- Melhorar a funcao de verificacao online.
  - Usar `urllib.parse.urlparse`.
  - Suportar URLs sem usuario e senha.
  - Suportar portas diferentes de `554`.

- Validar dados ao cadastrar camera.
  - Nome obrigatorio.
  - Nome e slug sem duplicidade.
  - URL RTSP valida.
  - MAC em formato valido.

- Tratar melhor erros de leitura e escrita do `cameras.json`.
  - Abrir com `encoding='utf-8'`.
  - Evitar que JSON invalido derrube painel ou captura sem mensagem clara.

- Substituir `except:` generico por excecoes especificas.
  - Registrar erros relevantes.
  - Evitar `except: pass` em trechos criticos.

- Decidir o uso do campo `protocolo`.
  - Opcao 1: salvar UDP/TCP no `cameras.json` e usar no FFmpeg.
  - Opcao 2: remover o campo da interface se ele nao sera usado.

- Melhorar gerenciamento dos logs do FFmpeg.
  - Evitar crescimento indefinido de `erro_<slug>.txt`.
  - Considerar rotacao simples ou limite de tamanho.

- Tornar `iniciar_nvr.sh` executavel e documentar o uso.
  - Comando: `chmod +x iniciar_nvr.sh`

## Prioridade baixa

- Criar `requirements.txt` com dependencias Python.

- Criar `README.md` com:
  - descricao do projeto;
  - requisitos;
  - instalacao;
  - execucao;
  - configuracao das cameras;
  - uso com Tailscale.

- Mostrar o caminho de armazenamento usado pelo sistema no painel.

- Melhorar mensagens no painel para:
  - camera offline;
  - falha no live stream;
  - ausencia de gravacoes;
  - disco perto do limite.

- Melhorar compatibilidade com dispositivos moveis.

## Melhorias futuras

- Criar uma tela de configuracoes do sistema.
  - Caminho de gravacoes.
  - Tempo de cada segmento.
  - Limite de limpeza do disco.
  - Transporte RTSP padrao.

- Centralizar configuracoes em arquivo unico ou `.env`.
  - Porta do Flask.
  - Caminho das gravacoes.
  - Limite de disco.
  - Transporte RTSP padrao.

- Melhorar a organizacao do backend.
  - Separar funcoes comuns em modulo auxiliar.
  - Reutilizar carregamento de cameras e resolucao de caminhos.

- Gerenciar processos com `systemd`.
  - Servico para painel.
  - Servico para captura.
  - Servico para limpeza.
  - Restart automatico em caso de falha.

- Adicionar edicao de cameras cadastradas.
  - Alterar nome.
  - Alterar URL RTSP.
  - Alterar MAC.
  - Alterar protocolo UDP/TCP.

- Adicionar botao para testar conexao da camera antes de salvar.

- Mostrar status detalhado por camera.
  - Online/offline.
  - Ultima gravacao.
  - Quantidade de videos.
  - Tamanho ocupado em disco.
  - PID do processo FFmpeg.

- Adicionar controle de captura por camera.
  - Pausar captura.
  - Retomar captura.
  - Reiniciar processo FFmpeg.

- Melhorar busca e filtros de gravacoes.
  - Filtrar por camera.
  - Filtrar por intervalo de horario.
  - Manter filtro por data.

- Adicionar exclusao manual de gravacoes pelo painel.

- Adicionar download em lote de gravacoes.

- Criar indicador de saude do sistema.
  - Uso de disco.
  - Quantidade de cameras online.
  - Status dos processos.
  - Ultimo erro registrado.

- Adicionar backup, importacao e exportacao de `cameras.json`.

- Considerar autenticacao opcional.
  - Nao e obrigatoria no uso atual via `localhost` ou Tailscale.
  - Deve ser adicionada antes de qualquer exposicao fora de rede privada confiavel.
