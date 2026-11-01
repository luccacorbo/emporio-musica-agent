# Dados do projeto

Esta pasta contém os arquivos de dados disponibilizados no desafio técnico AI Engineer 2026, proposto para o desenvolvimento de um agente de atendimento ao cliente do Empório da Música.

Os arquivos são utilizados como fontes de informação para as consultas realizadas pelo agente.

## Estrutura

```text
data/
├── raw/
│   ├── categories.csv
│   ├── customers.csv
│   ├── order_items.csv
│   ├── orders.csv
│   ├── politicas_da_loja.pdf
│   ├── products.csv
│   └── promotions.csv
└── README.md
```

## Utilização no projeto

Os arquivos CSV serão utilizados como fonte estruturada para consultas determinísticas, incluindo:

- Busca de produtos, preços e disponibilidade.
- Consulta de informações e status de pedidos.
- Recuperação de informações relacionadas a clientes, categorias e promoções.

O PDF será utilizado como fonte documental para responder perguntas relacionadas às políticas e aos procedimentos da loja, por meio de um mecanismo de recuperação de contexto (RAG).

## Integridade dos dados

Os arquivos originais são mantidos em `raw/` para preservar as fontes disponibilizadas no desafio.

Qualquer carregamento, transformação ou preparação necessária para as consultas será realizado pela aplicação, sem modificar os arquivos originais.

