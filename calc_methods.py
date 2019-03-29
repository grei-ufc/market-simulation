from numpy import linspace, exp

def demand_curve(t0=0.0, t1=5.0, tm=None, ymax=1.0, ymin=0.0, k=6.0):
    '''calcula os pontos da curva de demanda
    
    parametros
    ----------

    t0 : preço mínimo de compra/venda 
    t1 : preço máximo de compra/venda
    ymin : valor mínimo de demanda
    ymax: valor máximo de demanda
    k : inclinação da função logística
    '''
    if not tm:
        tm = t0 + (t1 - t0) / 2.0 # ponto medio da curva

    t = linspace(t0, t1, 50)
    y = ymax * (1.0 / (1.0 + exp(k*(t - tm)))) + ymin * (1.0 / (1.0 + exp(-k*(t - tm))))
    return t, y

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
