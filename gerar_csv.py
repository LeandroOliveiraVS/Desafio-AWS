import csv

with open("contas.csv", "w", newline="", encoding="utf-8") as arquivo:
    escritor = csv.writer(arquivo)
    escritor.writerow(["id_conta", "cod_agencia", "cnpj"])

    for i in range(1, 1001):
        id_conta = f"{i:04d}"
        cod_agencia = f"{1000 + i:04d}"
        cnpj = f"0CNPJ{id_conta}A"
        escritor.writerow([id_conta, cod_agencia, cnpj])
