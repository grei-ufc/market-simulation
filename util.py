"""Some useful functions."""

import datetime as dt


def generate_timeseries(start, time, step):
    '''
        start = string em formato datetime: dd/mm/YYYY - hh:mm:ss
        time = tamanho da série temporal em segundos
        step = step de tempo em minutos
    '''
    time_step = step * 60 # seconds
    dt_start = dt.datetime.strptime(start, '%d/%m/%Y - %H:%M:%S')
    delta = dt.timedelta(0, time)

    delta_sec = delta.days * (24 * 60 * 60) + delta.seconds

    res = [dt_start + dt.timedelta(0, t) for t in range(0, delta_sec, time_step)]
    res_pp = [i.strftime('%D - %T') for i in res]
    return res_pp
