# Melhorias do Projeto NVRBox

Este arquivo e o controle unico das melhorias planejadas. Quando uma tarefa for concluida, marque a caixa correspondente com `[x]`, ajuste a descricao se o comportamento final mudar e mova a entrada para a secao `Concluidas`.

## Foco atual

Manter o NVRBox leve, local e robusto para rodar em hardware simples:

- PC Linux.
- TV Box ou mini PC ARM.
- Android via Termux.

O sistema continua sem tela de login por enquanto, pois o uso previsto e em rede local confiavel. Docker fica para uma etapa futura, depois de validar bem o funcionamento em PC, ARM e Termux.

## Auditoria de 2026-09-24

Analise do codigo com testes reais. Os itens marcados como **comprovado** foram reproduzidos em teste; os numeros abaixo foram medidos em um PC de 16 nucleos, entao em TV Box ARM o tempo tende a ser varias vezes maior.

Resumo do que foi medido:

| Situacao | Tempo medido |
| --- | --- |
| Um `ffprobe` em um segmento | ~57 ms |
| Lista de 1 dia (144 videos), primeira vez | 11,1 s |
| Lista de 1 dia, segunda vez (cache) | 0,006 s |
| Lista completa da camera (1500 videos), primeira vez | 85 s |
| Lista completa, segunda vez | 85 s (cache nao funciona) |
| Painel inicial com 2 cameras offline | ~1 s |
| Status de uma camera offline | ~1 s |
| Processos parados (captura + limpeza + servidor) | ~75 MB de RAM, 0% CPU |

Conclusao: o sistema parado e leve. O peso aparece sob demanda, principalmente na listagem de gravacoes, que chama `ffprobe` arquivo por arquivo.

## Evidencias no equipamento real (2026-09-24)

Inspecao somente leitura da maquina que roda o NVRBox em producao, sem alterar nada:

- Hardware: Orange Pi PC Plus (ARMv7, 4 nucleos, 1 GB de RAM), Armbian, cartao de 7 GB para o sistema e HD externo de 458 GB em `/mnt/hd_externo`.
- Servico `nvrbox.service` (systemd, `Restart=always`) roda `iniciar_nvr.sh` com o `venv/` do projeto. Codigo no mesmo commit do repositorio (`afe402b`).
- 3 cameras (Garagem `.4`, Quintal `.3`, Lateral casa `.2`), todas UDP, perfil `onvif1`, **nenhuma com MAC salvo**. Segmentos de 15 minutos.

O que foi encontrado:

| Problema | Evidencia | Item |
| --- | --- | --- |
| As 3 cameras ficaram ~5 dias sem gravar | Ultimos arquivos em 16/09 entre 03:04 e 04:49; proximos so em 21/09 02:33. Os FFmpeg ficaram vivos e travados (contador de frames parado no log) ate morrerem sozinhos em 21/09 02:32, quando o watchdog finalmente reiniciou. | 1, 2 |
| `lateral_casa` sem gravar ha 3 dias, agora | Ultimo arquivo `lateral_casa_2026-09-21_03-48-56.mp4`, parado em 14 MB. Processo FFmpeg vivo, conexao TCP com `192.168.0.2:554` aberta, contador de frames parado (`time=01:19:03.35` repetido). A camera responde ping e a porta RTSP esta aberta. Nada no painel indica o problema. | 1, 2 |
| Lista de gravacoes muito lenta | Um `ffprobe` leva **~4,3 s por arquivo** no Orange Pi (segmentos de 15 min, 2304x1296, ~49 MB). 1 dia = 96 arquivos = ~7 min; historico da Garagem (811 arquivos) = ~58 min. O calendario, que nao usa `ffprobe`, responde em 0,1 s. | 5 |
| Logs do FFmpeg crescem sem limite | 547 MB em logs: cerca de 142 MB por camera no log anterior e 49 MB no atual. O FFmpeg escreve uma linha de progresso por frame e a rotacao so acontece quando ele reinicia. Mesmo travado, continua escrevendo a mesma linha. | 8 |
| Uso alto de CPU na gravacao | Os FFmpeg de gravacao aparecem entre 22% e 87% de CPU mesmo com `-c:v copy`. As cameras enviam audio `pcm_alaw` (G.711, 16 kHz mono), que o MP4 nao aceita bem, entao a conversao para AAC e necessaria enquanto houver audio (e e barata nessa taxa). A causa principal do CPU ainda precisa ser medida (recepcao RTP/UDP de 2304x1296 a 15 fps, `-fflags +genpts+igndts`). | 11 |
| Perda de pacotes no UDP | Logo apos reiniciar, o log da Lateral casa ja mostra `error while decoding MB ... bytestream -11`, sinal de pacote RTP perdido. Todas as cameras usam UDP. | 15 |
| Cameras trocadas (confirmado pelo usuario) | A camera cadastrada como "Lateral casa" (`.2`) grava o quintal e a "Quintal" (`.3`) grava a lateral. Quadros de 11/09, 15/09, 16/09, 21/09 e 24/09 mostram a mesma cena em cada nome desde a primeira gravacao (11/09 00:32): a troca ja existia antes do NVR comecar a gravar (IPs trocados no cadastro ou redistribuidos pelo roteador antes disso). Todo o historico dessas duas cameras esta com o nome invertido, mas de forma consistente (sem mistura dentro de um mesmo nome). Sem MAC salvo, o sistema nao tinha como perceber. Os MACs atuais estao na tabela ARP do Orange Pi. | 4 |

Reinicio do servico em 2026-09-24 12:47 (autorizado): as 3 cameras reconectaram em ~1 s e os segmentos novos cresceram normalmente (~6 MB a cada 45 s por camera). A Lateral casa voltou a gravar depois de 3 dias parada, o que confirma que o problema era o FFmpeg travado e nao a camera. Quadros extraidos das gravacoes novas mostram imagens coerentes com cada nome (garagem, quintal, lateral), mas a identidade de cada camera deve ser confirmada pelo usuario, ja que nao ha MAC salvo.

Observacao: o painel mostra as cameras como "online" porque a porta RTSP responde, mesmo com a gravacao parada ha dias. Isso confirma que o status atual nao serve para saber se a camera esta gravando.

## Prioridade critica

Problemas que causam perda de gravacao, perda de dados ou deixam o painel inutilizavel.

- [ ] 4. Encontrar a camera sozinho quando o IP mudar (identificar pelo MAC, nao pelo IP).
  - Sintoma relatado: quando falta energia ou o Wi-Fi reinicia, o roteador distribui os IPs de novo e as cameras podem trocar de IP entre si (ex.: camera 1 fica com o IP que era da camera 2 e vice-versa). O sistema continua usando o IP salvo, entao a gravacao da camera 2 vai para o nome da camera 1, e a pagina da camera 1 mostra a imagem da camera 2. Se o IP novo nao for de nenhuma camera cadastrada, a camera some.
  - Causa: o IP fica fixo dentro da `rtsp_url` salva em `cameras.local.json`. O campo `mac` ja existe no cadastro, mas so e validado no formulario; nenhuma parte do sistema usa o MAC para achar ou conferir a camera.
  - Requisito: tudo deve ser automatico. O usuario nao deve precisar de conhecimento tecnico, nem acessar o roteador ou outro sistema. Reserva de IP no roteador nao e solucao para este projeto.
  - Solucao, toda dentro do NVRBox:
    1. Cadastro sem digitar IP nem MAC: o painel procura as cameras na rede (descoberta ONVIF + varredura leve da porta RTSP) e mostra a lista das encontradas. O usuario escolhe a camera, da um nome e digita so a senha. O MAC e capturado automaticamente e salvo; o IP vira apenas "ultimo IP conhecido". Manter o cadastro manual por IP como opcao avancada.
    2. Conferencia antes de gravar: antes de iniciar cada FFmpeg e a cada ciclo do watchdog, conferir se o IP salvo ainda pertence ao MAC da camera, lendo a tabela ARP (`/proc/net/arp` ou `ip neigh`). Se nao pertencer, nao gravar com aquele IP (evita gravacao trocada).
    3. Busca automatica: se o MAC nao estiver no IP salvo, varrer a rede local de forma leve para achar o IP atual daquele MAC, atualizar o cadastro e remontar a `rtsp_url` sozinho. Nenhuma acao do usuario.
    4. Onde a tabela ARP nao estiver disponivel (Android 10+/Termux), usar a descoberta ONVIF (WS-Discovery, multicast UDP `239.255.255.250:3702`) com o identificador unico de cada camera. Muitas cameras (Intelbras, Hikvision, Dahua, XM) respondem.
  - Painel em linguagem simples: mostrar "Camera 1 mudou de endereco e foi reconectada automaticamente" ou "Camera 1 nao encontrada na rede. Verifique se ela esta ligada". Nunca pedir para o usuario configurar IP ou roteador. Registrar tambem no log e no estado do item 2.
  - Cameras ja cadastradas sem MAC: preencher o MAC automaticamente na primeira vez que a camera responder no IP salvo, sem pedir nada ao usuario.
  - Limitacoes a tratar:
    - Descoberta e tabela ARP so funcionam com o NVR na mesma rede local das cameras (nao atravessam outro roteador nem Tailscale).
    - Repetidores Wi-Fi que fazem "MAC NAT" podem mostrar o MAC do repetidor em vez do da camera; detectar MAC repetido em varias cameras e usar o identificador ONVIF nesse caso.
    - A busca deve ser leve (so quando a camera sumir, com limite de tempo e sem varrer a rede o tempo todo), pensando em hardware simples.
  - Teste: simular duas cameras trocando de IP e confirmar que cada gravacao continua no nome correto e que a pagina de cada camera mostra a camera certa.

- [ ] 5. Deixar a lista de gravacoes rapida.
  - Sintoma relatado: os videos ja gravados demoram a aparecer no painel da camera.
  - Causa (**comprovado**): a tela da camera carrega por padrao a lista **sem filtro de data**, ou seja, todo o historico. Para cada arquivo roda um `ffprobe` em sequencia. Com 1500 videos a resposta levou 85 s.
  - Causa (**comprovado**): o cache `VIDEO_INFO_CACHE` e zerado quando passa de 1000 itens. Com mais de 1000 videos ele se apaga durante a propria listagem e nunca ajuda: a segunda chamada tambem levou 85 s.
  - O cache fica so em memoria e se perde a cada reinicio do servidor.
  - Abrir a tela ja filtrada no dia mais recente com gravacao (o calendario ja sabe quais dias existem).
  - Paginar a lista (ex.: 50 por pagina).
  - Nao rodar `ffprobe` na listagem: usar nome, tamanho e data do arquivo; validar apenas ao abrir o video ou em segundo plano.
  - Segmentos fechados podem ter duracao estimada pelo tempo de segmento; so o ultimo segmento de cada camera precisa de verificacao especial.
  - Se o cache continuar, usar limite com remocao dos mais antigos (LRU) em vez de apagar tudo, e opcionalmente persistir em disco.
  - Substitui a antiga tarefa "Validar gravacoes sem deixar o painel pesado".

- [ ] 6. Impedir que a limpeza apague arquivos que nao sao do NVR.
  - `limpeza.py` apaga qualquer `.mp4` com mais de 15 minutos na pasta ativa. Como o painel aceita qualquer pasta como armazenamento, apontar para `~/Videos` pode apagar videos pessoais.
  - Limitar a limpeza a arquivos no padrao `<slug>_AAAA-MM-DD_HH-MM-SS.mp4`.
  - Se o disco estiver acima do limite por causa de outros arquivos, a limpeza apaga todo o historico ate nao sobrar nada elegivel. Definir um minimo de gravacoes preservadas ou limitar pelo espaco usado pelas proprias gravacoes, e avisar no painel.
  - Restringir `/configurar_armazenamento` as opcoes listadas por `listar_armazenamentos()`, em vez de aceitar qualquer caminho digitado.

- [ ] 7. Proteger as acoes do painel contra CSRF.
  - **Comprovado**: um `POST` com `Origin` de outro site foi aceito. Qualquer pagina aberta no navegador pode enviar formulario oculto para `127.0.0.1:5000` e apagar cameras, apagar todos os videos ou trocar o armazenamento.
  - A autenticacao basica nao resolve, porque o navegador reenvia a senha automaticamente.
  - Adicionar token CSRF nos formularios ou, no minimo, rejeitar `POST` cujo `Origin`/`Referer` nao seja o proprio painel.

## Prioridade alta

- [ ] 9. Corrigir a contagem de videos no painel inicial.
  - **Comprovado**: `montar_contexto_index` usa `startswith(slug)`. Com cameras `sala` e `sala_2`, as duas mostraram 3 videos (correto: 1 e 2), porque `sala_2026-...` tambem comeca com `sala_2`.
  - Usar `nome_video_pertence_camera`, como ja fazem as outras telas.
  - Adicionar teste com slugs que sao prefixo um do outro.

- [ ] 10. Nao travar o painel inicial esperando cameras offline.
  - `montar_contexto_index` testa cada camera em sequencia com timeout de 1 s. Com varias cameras offline a pagina demora varios segundos.
  - Carregar o status por API assincrona (como a tela da camera ja faz) ou testar em paralelo com cache curto.
  - Dentro disso, diferenciar porta aberta, RTSP valido, senha/perfil incorreto, timeout e camera sem video, usando `ffprobe` com timeout curto e cache.

- [ ] 11. Reduzir uso de CPU em hardware fraco.
  - A captura converte o audio para AAC (`-c:a aac`) em todas as cameras, o tempo todo. As cameras do equipamento real enviam `pcm_alaw` (G.711), entao a conversao e necessaria para manter audio no MP4. Usar `-c:a copy` so quando a camera ja enviar AAC e permitir desativar audio por camera (`-an`). Medir antes de otimizar: o maior custo de CPU observado provavelmente nao e o audio.
  - O live view decodifica e reencoda em MJPEG um FFmpeg por visualizacao. Duas abas na mesma camera sao dois processos. Compartilhar um processo por camera entre os espectadores e encerrar quando ninguem estiver assistindo.
  - A rota `/video_compativel` reencoda para WebM (libvpx) sem limite de processos simultaneos; em ARM isso e muito pesado. Limitar a um processo por vez e considerar remux (`-c copy`) antes de reencodar.
  - Permitir escolher stream principal ou substream por camera.
  - Manter `-c:v copy` na gravacao.

- [ ] 12. Corrigir e reforcar o script de inicializacao.
  - `iniciar_nvr.sh` usa o `python3` do sistema; em distros que bloqueiam `pip` global (ex.: Arch) o Flask fica so no `.venv` e o painel nao sobe. Usar `.venv/bin/python` quando existir.
  - O script so acompanha o servidor. Se `captura.py` ou `limpeza.py` morrerem, nada percebe. Reiniciar automaticamente ou refletir no estado do item 2.
  - Ao encerrar o servidor, processos FFmpeg de live view e de `/video_compativel` podem ficar orfaos. Encerrar o grupo de processos.
  - Adicionar comandos `start`, `stop`, `restart` e `status`.
  - Verificar FFmpeg e ffprobe antes de iniciar.
  - Mostrar IP local de acesso ao painel.

- [ ] 13. Validar `NVRBOX_TEMPO_SEGMENTO`.
  - **Comprovado**: `NVRBOX_TEMPO_SEGMENTO=-5` e aceito e repassado ao FFmpeg. Aplicar a mesma validacao do painel (5, 10 ou 15 minutos) ou ao menos exigir valor positivo.
  - Tratar valores invalidos em `NVRBOX_LIMITE_DISCO`, `NVRBOX_TIMEOUT_TESTE_RTSP` e `NVRBOX_FFMPEG_LOG_MAX_BYTES`, que hoje derrubam o sistema na importacao.

## Prioridade media

- [ ] 14. Remover dependencia de internet na interface.
  - Os icones vem de CDN (unpkg). Sem internet, botoes que so tem icone (apagar, tela cheia, navegacao do calendario) ficam vazios.
  - Substituir CDN de icones por arquivos locais em `static/`.
  - Garantir que o painel funcione sem internet em TV Box e Termux.

- [ ] 15. Melhorar confiabilidade do RTSP.
  - Manter UDP/TCP por camera; o padrao atual e UDP, que perde pacotes com facilidade em Wi-Fi.
  - Evidencia (2026-09-24, com o log limpo apos o item 8): nas 3 cameras do Orange Pi aparecem continuamente `RTP: missed N packets`, `Too short data for FU-A H.264 RTP packet` e `max delay reached`, ou seja, perda de pacotes UDP que gera quadros corrompidos na gravacao. Sao cerca de 9 KB de avisos a cada 3,5 minutos por camera. Testar TCP nessas cameras e prioridade dentro deste item.
  - Recomendar TCP quando houver perda de pacotes. As cameras do equipamento real sao genericas (servidor RTSP `RtspServer_0.0.0.2`), com Wi-Fi e firmware simples; TCP ajuda porque retransmite o que se perde, enquanto UDP simplesmente descarta.
  - Detectar mensagens comuns nos logs do FFmpeg, como perda RTP.
  - Mostrar sugestao clara no painel quando uma camera estiver instavel.

- [ ] 16. Evitar perda de cadastro por gravacoes simultaneas.
  - `cameras.local.json` e lido e reescrito sem trava. Duas abas salvando ao mesmo tempo podem perder uma alteracao.
  - Usar trava de arquivo (`fcntl.flock`) na leitura-modificacao-escrita.

- [ ] 17. Melhorar erros e avisos no painel.
  - JSON de cameras invalido.
  - Pasta de gravacao sem permissao (ver item 3).
  - FFmpeg ou ffprobe ausente.
  - Camera sem gravacao recente (ver item 2).
  - Disco perto do limite.
  - Falha no live view.
  - Remover camera inexistente hoje responde "Camera removida."; responder com erro.

- [ ] 18. Criar tela de saude do sistema.
  - FFmpeg e ffprobe instalados.
  - Captura e limpeza ativas.
  - Ultima gravacao e ultimo erro por camera.
  - Uso de disco e pasta ativa de gravacao.
  - Reaproveitar o arquivo de estado do item 2.

- [ ] 19. Melhorar armazenamento portatil.
  - Validar melhor Linux, TV Box e Android via Termux.
  - Detectar `$HOME/storage/shared` quando existir.
  - Detectar `/storage/emulated/0` e caminhos equivalentes.
  - Adicionar botao ou acao de testar escrita.
  - Sem caminho salvo, fixar o primeiro disco detectado em `sistema.json` para a gravacao nao mudar de lugar ao plugar outro pendrive (restante do item 3).

- [ ] 20. Ampliar os testes automatizados.
  - Hoje os testes do servidor cobrem apenas o calendario.
  - Cobrir validacao de cadastro/edicao, bloqueio de caminho fora da pasta (`obter_caminho_video_seguro`), exclusao de videos, contagem por camera, caminho de gravacao invalido e deteccao de gravacao travada.

## Prioridade baixa

- [ ] 21. Otimizar a limpeza com muitos arquivos.
  - `executar_limpeza` relista e reordena a pasta inteira a cada arquivo apagado. Listar uma vez e apagar em sequencia ate voltar ao limite.

- [ ] 22. Remover codigo sem uso.
  - `get_disk_info` e `contar_arquivos` em `servidor.py`.
  - Efeito colateral em `config.py`: `CAMINHO_VIDEOS` e `TEMPO_SEGMENTO` sao calculados na importacao e testam escrita em discos externos mesmo quando nao sao usados.

- [ ] 23. Organizar o backend em modulos menores.
  - Separar cameras, RTSP, videos, armazenamento e status.
  - Manter `servidor.py` mais focado nas rotas Flask.
  - Evitar refatoracao grande antes das melhorias de confiabilidade.

- [ ] 24. Melhorar lista de gravacoes.
  - Ordenacao por data/hora.
  - Manter botoes de player, download e apagar.
  - Paginacao e duracao entram no item 5.

- [ ] 25. Adicionar backup e restauracao.
  - Exportar cameras.
  - Importar cameras.
  - Exportar configuracoes locais sem expor credenciais indevidamente.

- [ ] 26. Adicionar recuperacao de videos invalidos.
  - Tentar remux com FFmpeg.
  - Preservar arquivo original.
  - Mostrar resultado da tentativa no painel.

- [ ] 27. Nao expor a senha RTSP na lista de processos.
  - A URL RTSP com senha aparece completa nos argumentos do FFmpeg (`ps`), visivel para qualquer usuario da maquina.
  - Avaliar passar credenciais de outra forma ou, no minimo, rodar o servico com um usuario proprio em vez de `root`.

## Futuro

- [ ] Avaliar Docker depois da base ficar robusta.
  - Confirmar se Docker ajuda no PC Linux.
  - Confirmar limitacoes em TV Box ARM.
  - Confirmar se Android via Termux deve continuar sem Docker.

- [ ] Criar instalador simples.
  - Instalar dependencias quando possivel (incluindo `.venv`).
  - Verificar FFmpeg e ffprobe.
  - Criar pastas locais.
  - Criar `cameras.local.json` inicial quando nao existir.
  - Testar permissao de escrita.

## Ordem recomendada de execucao

1. ~~Gravacao travada e estado de gravacao (itens 1, 2 e 8)~~: concluido em 2026-09-24.
2. Caminho de gravacao (item 3, concluido) e identificacao da camera por MAC (item 4): evitam gravar no lugar errado.
3. Lista de gravacoes rapida (item 5).
4. Seguranca dos dados (itens 6 e 7).
5. Correcoes rapidas (itens 9, 12 e 13).
6. Desempenho em hardware fraco (itens 10 e 11).
7. Itens de prioridade media e baixa.
8. Recomeco em producao: apagar gravacoes antigas e gravar do zero (secao abaixo).

## Recomeco em producao (depois das melhorias)

Decisao do usuario (2026-09-24): nao corrigir nem renomear o historico atual. Depois que as melhorias estiverem aplicadas, apagar todas as gravacoes e comecar a gravar do zero.

- [ ] Aplicar as melhorias no Orange Pi (atualizar o codigo em `/root/Repository/NVR-BOX` e reiniciar `nvrbox.service`).
- [ ] Parar o servico antes de apagar, para nenhum FFmpeg estar escrevendo.
- [ ] Apagar todas as gravacoes em `/mnt/hd_externo/gravacoes` (`garagem_*`, `quintal_*`, `lateral_casa_*`) e os logs `erro_*.txt` e `erro_*.txt.1` (~547 MB).
- [ ] Recadastrar ou revisar as 3 cameras ja com a identificacao por MAC (item 4), conferindo pela imagem ao vivo que cada nome mostra o lugar certo. Hoje "Lateral casa" (`.2`) e "Quintal" (`.3`) estao invertidas.
- [ ] Subir o servico e confirmar no painel que as 3 cameras aparecem como "Gravando" (item 2).
- [ ] Acompanhar os primeiros dias: nenhuma camera parada, logs pequenos, lista de gravacoes abrindo rapido.

## Concluidas

- [x] 3. Verificar corretamente o caminho de gravacao.
  - Sintoma relatado: o sistema nao verifica direito o caminho de gravacao.
  - **Comprovado**: se o caminho salvo estiver em uma memoria removida sem permissao (ex.: pendrive em `/run/media/...`), o `servidor.py` nao sobe (`PermissionError` na importacao), o `limpeza.py` morre e o `captura.py` fica vivo sem gravar nada, apenas imprimindo `Erro no Watchdog` a cada 30 s.
  - **Comprovado**: se o HD externo estiver desmontado mas a pasta pai for gravavel (ex.: `/mnt/hd`), `garantir_diretorios` cria a pasta no disco interno e a gravacao segue no lugar errado, sem aviso, podendo encher o disco do sistema.
  - `encontrar_armazenamento()` nao testa escrita no caminho salvo ou vindo de ambiente; so testa na deteccao automatica.
  - A deteccao automatica pega o primeiro disco externo gravavel; ao plugar um pendrive, a gravacao pode mudar de lugar sozinha.
  - Para caminhos externos, exigir que a base seja um ponto de montagem real (`os.path.ismount`) e nunca criar a pasta se o disco nao estiver montado.
  - Nao derrubar servidor e limpeza por caminho invalido: iniciar em modo de erro e mostrar o problema no painel.
  - Validar escrita periodicamente e expor o resultado no estado do item 2.
  - Feito em 2026-09-24: `verificar_armazenamento()` exige que discos em `/media`, `/mnt`, `/storage` e `/run/media` estejam montados dentro da raiz (evita o falso positivo do `/run` ser tmpfs) e nunca cria a pasta com o disco ausente; `garantir_diretorios()` levanta `ArmazenamentoIndisponivel` com mensagem para o usuario; servidor e limpeza nao caem mais; captura para os FFmpeg, registra o motivo uma vez e retoma sozinha; painel mostra "Nao e possivel gravar". Escolher pelo painel um HD desconectado e recusado.
  - Pendente (movido para o item 19): a deteccao automatica sem caminho salvo ainda pega o primeiro disco externo encontrado, entao plugar um pendrive pode mudar o destino quando nada foi escolhido no painel.

- [x] 1. Detectar gravacao travada e reiniciar a captura.
  - Sintoma relatado: as gravacoes param sem motivo aparente.
  - Causa (**comprovado**): nenhum comando `ffmpeg` tem timeout de rede. Uma camera que aceita a conexao mas para de enviar video deixa o FFmpeg travado indefinidamente; no teste ele ficou preso ate ser morto externamente.
  - Causa: `captura.py` so verifica se o processo existe (`poll()`), nunca se novos arquivos estao sendo gerados. Processo travado e considerado saudavel e nunca e reiniciado.
  - Adicionar `-timeout` (RTSP, em microssegundos) nos comandos de captura, live view e teste de cadastro.
  - No watchdog, verificar o `mtime`/tamanho do ultimo segmento de cada camera; se nao crescer por um tempo limite (ex.: 60 s), encerrar e reiniciar o FFmpeg.
  - Reduzir o intervalo do watchdog de 30 s para algo menor, ou reagir logo que o processo morrer, para diminuir o buraco na gravacao.
  - Registrar em log o motivo de cada reinicio.
  - Sinal pronto para usar: mesmo travado, o FFmpeg continua escrevendo progresso com o mesmo `frame=`/`time=`. Comparar o tamanho do segmento atual (ou o `time=`) entre ciclos detecta o travamento sem custo de CPU.
  - Ao reiniciar uma camera travada, nao depender dela morrer sozinha: no equipamento real isso levou ~5 dias.
  - Feito em 2026-09-24: `-timeout` RTSP (com deteccao de `-stimeout` em FFmpeg antigo e limite de 2000 s), vigia a cada 10 s que mede o crescimento do arquivo aberto pelo FFmpeg (`/proc/<pid>/fd`, com fallback pelo nome), reinicio apos 60 s sem crescer ou 90 s sem primeiro video, intervalo minimo de 30 s entre tentativas e relogio monotonico. Testado com camera falsa (MediaMTX congelado por `docker pause`): travamento detectado e gravacao retomada sozinha.

- [x] 2. Mostrar no painel se cada camera esta gravando ou parada.
  - Sintoma relatado: o sistema nao reconhece se as gravacoes pararam.
  - Hoje nao existe nenhum indicador de gravacao; o status "online" so testa a porta RTSP.
  - `captura.py` deve gravar um arquivo de estado (ex.: `.run/estado_captura.json`) com, por camera: gravando/parada, hora do ultimo segmento, numero de reinicios e ultimo erro do FFmpeg.
  - Painel e tela da camera devem mostrar "Gravando", "Parada ha X min" e o ultimo erro.
  - Alertar quando o proprio processo de captura nao estiver rodando (estado desatualizado).
  - Em producao no Orange Pi desde 2026-09-24 14:18: as 3 cameras aparecem como `Gravando` no painel.
  - Feito em 2026-09-24: `.run/estado_captura.json` com estado, ultima gravacao, reinicios, ultimo motivo e ultimo erro (senha mascarada); painel inicial mostra `Gravando`, `Conectando...`, `Sem gravar ha X` por camera e aviso geral quando a captura nao esta rodando; tela da camera ganhou o card `Gravacao` com o ultimo erro. Estado gravado sem `fsync` e no maximo a cada 60 s quando nada muda.

- [x] 8. Preservar o log de erro do FFmpeg entre reinicios.
  - `iniciar_ffmpeg` abre o log com `"w"`, que zera o arquivo a cada reinicio. O erro que causou a queda se perde.
  - Abrir em modo de acrescimo (`"a"`) com marca de data/hora por inicio, mantendo a rotacao por tamanho.
  - Usar `-nostats -loglevel warning` na captura para registrar so avisos e erros, em vez de uma linha de progresso por frame (no equipamento real foram ~140 MB por camera em 5 dias).
  - Rotacionar o log tambem com o FFmpeg rodando, nao so ao reiniciar.
  - Feito em 2026-09-24: log em modo de acrescimo com cabecalho por inicio, `-nostats -loglevel warning`, rotacao por copia e truncamento tambem com o FFmpeg rodando. No teste, o log de uma sessao com travamento e reinicio ficou com 92 bytes.

- [x] Corrigir a reproducao de videos ja gravados.
  - Tentar tocar primeiro o `.mp4` original salvo na pasta.
  - Usar `/video_compativel/<arquivo>` somente como fallback.
  - Evitar que o video salvo pareca um stream que vai carregando aos poucos.
  - Mostrar a duracao completa obtida por `ffprobe`.
  - Manter cache em memoria para metadados dos videos; cache persistente de WebM fica para depois se o fallback ainda pesar em hardware fraco.

- [x] Criar tela de mosaico para ver todas as cameras ao vivo.
  - Adicionar botao `Ver todas` no painel principal.
  - Mostrar grade responsiva com todas as cameras.
  - Exibir nome e status em cada camera.
  - Clicar em uma camera deve abrir a tela individual.
  - Adicionar pausa/retomada geral para fechar os streams quando o mosaico nao estiver em uso.

- [x] Adicionar exclusao manual de gravacoes.
  - Apagar um video especifico.
  - Apagar todos os videos de uma camera.
  - Usar somente rotas `POST`.
  - Exigir confirmacao antes de apagar.
  - Permitir apagar apenas arquivos `.mp4` dentro da pasta de gravacoes ativa.
  - Para apagar todos de uma camera, limitar aos arquivos que comecam com o slug da camera e preservar arquivos recentes ou em gravacao.

- [x] Reforcar e testar a limpeza automatica.
  - Confirmar que apaga quando o disco passa do limite configurado.
  - Confirmar que o padrao de 90% funciona.
  - Confirmar que remove primeiro os videos mais antigos.
  - Confirmar que preserva videos novos e segmentos em gravacao.
  - Garantir que a limpeza so atua dentro da pasta de gravacoes ativa.
  - Garantir que a limpeza so apaga arquivos `.mp4`.
  - Registrar em log claro o que foi apagado e cobrir o comportamento com testes automatizados.

- [x] Criar calendario interativo de gravacoes.
  - Mostrar dias com gravacoes.
  - Mostrar dias sem gravacoes.
  - Exibir quantidade de videos por dia.
  - Permitir clicar no dia para filtrar a lista.
  - Manter filtro por data simples como fallback.

- [x] Permitir escolher o tempo dos segmentos pelo painel.
  - Opcoes iniciais: 5, 10 e 15 minutos.
  - Salvar escolha em `sistema.json`.
  - Fazer `captura.py` detectar alteracao e reiniciar FFmpeg para aplicar o novo tempo.
  - Manter variavel `NVRBOX_TEMPO_SEGMENTO` como override opcional.
