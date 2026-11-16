#!/bin/bash
# Roda os 54 experimentos do TP2 (3 metodos x 6 quantidades x 3 situacoes)
# e grava as metricas em resultados.csv.
# Uso: ./experimentos.sh            (compila antes, se preciso)
set -e
cd "$(dirname "$0")"
make -s ordena

SAIDA=resultados.csv
echo "metodo,n,situacao,leituras,escritas,comparacoes,tempo" > "$SAIDA"

for metodo in 1 2 3; do
  for n in 100 200 2000 20000 200000 471705; do
    for situacao in 1 2 3; do
      out=$(./ordena "$metodo" "$n" "$situacao")
      # extrai o valor apos ':' de cada linha de metrica
      val() { echo "$out" | grep "$1" | sed 's/.*: *//; s/ .*//'; }
      linha="$metodo,$n,$situacao,$(val 'leitura'),$(val 'escrita'),$(val 'Comparacoes'),$(val 'Tempo')"
      echo "$linha" | tee -a "$SAIDA"
      # opcional: conferencia externa da saida (usada no desenvolvimento)
      if [ -n "$VERIFICA" ]; then $VERIFICA "$metodo" "$n" "$situacao"; fi
    done
  done
done
echo "Resultados gravados em $SAIDA"
