# language: pt
Funcionalidade: Vincular a torre à minha conta com o código do adesivo
  Como comprador de uma torre AeroTower
  Quero digitar o código do adesivo no app
  Para ver e controlar a minha torre pela minha conta

  Contexto:
    Dado uma torre do kit "pro" saiu da fábrica com um adesivo
    E a Ana entrou no app com a conta Google dela

  Cenário: Código do adesivo vincula a torre
    Quando a Ana digita o código do adesivo com o apelido "Varanda"
    Então a torre aparece na conta da Ana com o apelido "Varanda"
    E o Backend é avisado de que a torre foi vinculada

  Cenário: Código digitado em minúsculas e sem hífen também vale
    Quando a Ana digita o código em minúsculas e sem o hífen
    Então a torre aparece na conta da Ana

  Cenário: Torre que já tem dono não muda de conta
    Dado que o Bruno já vinculou essa torre
    Quando a Ana digita o código do adesivo com o apelido "Minha"
    Então a Ana vê a mensagem "já está associada a outro usuário"

  Cenário: Quem já tem uma torre não vincula a segunda
    Dado que a Ana já tem outra torre vinculada
    Quando a Ana digita o código do adesivo com o apelido "Segunda"
    Então a Ana vê a mensagem "Você já possui"

  Cenário: Desvincular para passar a torre adiante
    Dado que a Ana vinculou a torre
    Quando a Ana desvincula a torre
    E o Bruno digita o mesmo código do adesivo
    Então a torre aparece na conta do Bruno
