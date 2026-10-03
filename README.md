# GLOW-CUSTODY

**Classificação: CANDIDATE / PRE-H0 / NON-BEARER / NO OPERATIONAL AUTHORITY**

Bootstrap V0.1 preservado; V0.3 contém implementação candidata e testes offline, sem autoridade operacional.

## Finalidade

GLOW-CUSTODY é um repositório **candidato** a custodiante externo de operações do GLOW. Seu objetivo futuro é preservar **reservas de uso único** e **recibos verificáveis** para WorkMissions, começando pelo NEXT-001.

Este repositório **não** é um executor alternativo, **não** é um novo GLOW e **não** é uma nova WorkMission.

## Relação com mshigueoka/GLOW

O repositório principal é `mshigueoka/GLOW`. A governança H0/M0/M1/S0 do projeto permanece integralmente em vigor e integralmente preservada **lá**. Nada aqui a substitui, estende, emite ou reinterpreta.

## Separação de papéis

| Papel | Função | Estado neste bootstrap |
|---|---|---|
| Executor | Executa a operação (GLOW) | Fora do escopo deste repositório |
| Custodiante | Preserva reserva de uso único e recibos | **Candidato, não qualificado** |
| Testemunha independente (W038) | Observa e atesta o estado do custodiante | **Não qualificada, não instalada** |

Os três papéis devem possuir credenciais distintas e efetivamente separadas. O GLOW nunca poderá deter credencial capaz de alterar ou excluir arbitrariamente registros de custódia.

## Estado atual

Candidato **não qualificado**. A nova conta GitHub **não** foi qualificada como domínio de confiança independente. Contas distintas não comprovam, por si, independência administrativa.

## O que este repositório pode e não pode demonstrar

**Pode demonstrar:** a estrutura pretendida dos registros (schemas), propriedades desejadas (`CUSTODY_POLICY.md`) e comportamento do núcleo V0.3 sob testes offline e simulação.

**Não pode demonstrar:** execução operacional, reserva real, CAS real, anti-rollback, independência administrativa, emissão de H0/M0, efeitos de NEXT-001 ou qualquer evidência do experimento histórico E17.

Capacidade, autoridade e consequência observada são coisas distintas e permanecem separadas.

## Interfaces candidatas (implementadas em software, não ativadas operacionalmente)

- `reserve_exact_attempt` — tenta criar, de forma condicional e de uso único, a reserva de uma tentativa exata. Distingue primeira criação, reserva preexistente, falha e resultado desconhecido. `UNKNOWN` nunca autoriza repetição.
- `read_exact_attempt` — leitura **somente leitura** de uma tentativa exata, usada para reconciliar ACK desconhecido.

Contratos estruturais: `schemas/`.

## Etapas mínimas de qualificação antes de qualquer integração operacional

1. Revisão humana deste bootstrap.
2. Decisão do proprietário sobre configuração administrativa do repositório (proteções, acessos, contas).
3. Qualificação própria da independência administrativa do custodiante.
4. Qualificação da implementação de reserva condicional e de suas credenciais, com revisão independente.
5. Qualificação própria de uma testemunha W038 independente.
6. Evidência externa das propriedades alegadas, preservada separadamente.
7. Decisão de integração tomada **dentro** da governança de `mshigueoka/GLOW`.

Até a conclusão dessas etapas, nenhum resultado deste repositório pode ser promovido a evidência operacional.

## Conteúdo

- `CUSTODY_POLICY.md` — propriedades desejadas e limitações.
- `src/coal/` — núcleo candidato, sem operação real ativada.
- `schemas/` — quatro JSON Schemas (Draft 2020-12).
- `tests/` — testes sintéticos e validação dos schemas.
- `docs/` — arquitetura, ameaça, integração e qualificação.
- `.github/workflows/ci.yml` — exclusivamente CI de código, sem efeito de custódia.
