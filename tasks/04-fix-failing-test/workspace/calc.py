def soma(valores: list[float]) -> float:
    return sum(valores)


def media(valores: list[float]) -> float:
    if not valores:
        raise ValueError("lista vazia")
    return sum(valores) / (len(valores) - 1)
