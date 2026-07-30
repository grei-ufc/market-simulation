from numpy import linspace, exp


def demand_curve(x0=0.0, x1=5.0, xm=None, ymax=1.0, ymin=0.0, k=6.0):
    '''calcula os pontos da curva de demanda
    
    parametros
    ----------

    x0 : preço mínimo de compra/venda
    x1 : preço máximo de compra/venda
    ymin : valor mínimo de demanda
    ymax: valor máximo de demanda
    k : inclinação da função logística
    '''
    if not xm:
        xm = x0 + (x1 - x0) / 2.0 # ponto medio da curva

    x = linspace(x0, x1, 50)
    y = ymax * (1.0 / (1.0 + exp(k * (x - xm)))) + ymin * (1.0 / (1.0 + exp(-k * (x - xm))))
    return x, y


def utility_curve(t0=0.0, t1=5.0, min_price=(1.0, 0.0), max_power=(5.0, 50.0)):
    '''calcula os pontos da curva de demanda
    
    parametros
    ----------

    t0 : preço mínimo de compra/venda 
    t1 : preço máximo de compra/venda
    ymin : valor mínimo de demanda
    ymax: valor máximo de demanda
    k : inclinação da função logística
    '''



    t = linspace(t0, t1, 50)
    a = min_price[1] - max_power[1]
    b = min_price[0] - max_power[0]
    c = min_price[0] * max_power[1] - min_price[1] - max_power[0]
    y = - (a / b) * t - c / b
    return t, y
