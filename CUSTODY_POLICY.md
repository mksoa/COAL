# CUSTODY_POLICY

**Classificação: CANDIDATE / PRE-H0 / NON-BEARER / NO OPERATIONAL AUTHORITY**

## Convenção de status

Cada propriedade usa um de três status, que **não** se promovem automaticamente:

- **ESPECIFICADA** — descrita como desejada. Nada além disso.
- **IMPLEMENTADA** — existe mecanismo em funcionamento.
- **COMPROVADA (evidência externa)** — verificada por evidência independente do custodiante e do executor.

**No V0.1, todas as propriedades abaixo são apenas ESPECIFICADAS. Nenhuma é IMPLEMENTADA. Nenhuma é COMPROVADA.**

## Propriedades desejadas

| # | Propriedade | Especificada | Implementada | Comprovada |
|---|---|---|---|---|
| 1 | Reserva condicional de uso único | Sim | Não | Não |
| 2 | Identidade imutável da operação | Sim | Não | Não |
| 3 | Ausência de overwrite, reset, refund ou reutilização | Sim | Não | Não |
| 4 | Preservação integral dos recibos originais | Sim | Não | Não |
| 5 | Separação efetiva de credenciais GLOW × custodiante | Sim | Não | Não |
| 6 | Reconciliação exclusivamente read-only para ACK desconhecido | Sim | Não | Não |
| 7 | Proteção contra alterações administrativas não autorizadas | Sim | Não | Não |
| 8 | Limitações das garantias do GitHub reconhecidas | Sim | n/a | n/a |
| 9 | Testemunha W038 independente para alegações fortes de anti-rollback | Sim | Não | Não |

### 1. Reserva condicional de uso único
Uma tentativa exata só pode ser reservada uma vez. Uma segunda tentativa de reserva da mesma identidade resulta em "reserva preexistente", nunca em nova reserva.

### 2. Identidade imutável da operação
A operação é identificada por vínculo imutável (binding) com repositório, missão/sujeito, epoch, operation ID e digest. A identidade não pode ser reescrita após a reserva.

### 3. Ausência de overwrite, reset, refund ou reutilização
Reservas e recibos não são sobrescritos, reiniciados, estornados nem reutilizados.

### 4. Preservação integral dos recibos originais
O ACK original e o recibo original são preservados como foram emitidos. Reconciliações são registros novos e separados, nunca substituições.

### 5. Separação efetiva de credenciais
O GLOW não pode deter credencial capaz de alterar ou excluir arbitrariamente registros de custódia. Nenhuma credencial é compartilhada entre GLOW/MCM e o custodiante.

### 6. Reconciliação read-only
Diante de ACK desconhecido, a única ação permitida é leitura (`read_exact_attempt`). Resultado `UNKNOWN` **nunca** autoriza repetição, retry ou nova reserva.

### 7. Proteção contra alterações administrativas
Desejável, mas não garantida por este repositório. Ver limitações.

### 8. Limitações das garantias oferecidas por GitHub
- Contas GitHub distintas não comprovam automaticamente independência administrativa.
- Um repositório GitHub não é, por si só, armazenamento imutável contra todos os administradores.
- A criação condicional de uma referência não equivale automaticamente a um journal durável com anti-rollback.
- Histórico, tags e referências podem ser alterados por quem detenha privilégios suficientes, independentemente do desenho dos schemas.

### 9. Testemunha W038 independente
Alegações fortes de anti-rollback exigem uma testemunha W038 independente. A independência da W038 requer **qualificação própria** e não é presumida.

## Capacidade, autoridade e consequência observada

- **Capacidade**: o que uma credencial ou sistema consegue fazer tecnicamente.
- **Autoridade**: o que está autorizado a fazer pela governança.
- **Consequência observada**: o que de fato ocorreu, conforme evidência.

Uma não implica a outra. Este bootstrap não concede capacidade, não confere autoridade e não registra consequência.

## Limites deste bootstrap

- Nenhum resultado deste bootstrap pode ser promovido a evidência de execução operacional.
- Nenhum arquivo declara H0/M0 emitido, nem custódia independente qualificada.
- A governança H0/M0/M1/S0 de `mshigueoka/GLOW` permanece integralmente preservada e fora deste repositório.
- Nenhuma metodologia nova ou segunda engine de governança é introduzida.
