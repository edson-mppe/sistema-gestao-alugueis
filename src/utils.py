import pandas as pd
import holidays
from datetime import date, timedelta, datetime
from dateutil.easter import easter

def get_holidays(years=[2025, 2026]):
    """
    Retorna um DataFrame com os feriados dos anos especificados.
    Args:
        years: Um ano (int) ou uma lista de anos (list).
    Colunas: "Feriado", "Data", "Dia da Semana", "Mês", "Abrangência", "Feriadão"
    Abrangência: "Brasil", "Pernambuco", "Recife"
    Feriadão: "Sim" para Carnaval, Semana Santa e feriados em Seg/Sex.
    """
    if isinstance(years, int):
        years = [years]
        
    all_holidays_list = []
    
    dia_semana_map = {
        0: "Segunda-feira",
        1: "Terça-feira",
        2: "Quarta-feira",
        3: "Quinta-feira",
        4: "Sexta-feira",
        5: "Sábado",
        6: "Domingo"
    }
    
    mes_map = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }

    for year in years:
        # 1. Feriados Nacionais (Brasil)
        br_holidays = holidays.Brazil(years=year)
        
        # 2. Feriados Estaduais (Pernambuco)
        pe_holidays = holidays.Brazil(subdiv='PE', years=year)
        
        # 3. Feriados Municipais (Recife) e Outros Manuais
        manual_holidays = {}
        
        # Recife Fixos
        manual_holidays[date(year, 3, 12)] = ("Aniversário do Recife", "Recife")
        manual_holidays[date(year, 6, 24)] = ("São João", "Recife")
        manual_holidays[date(year, 7, 16)] = ("Nossa Senhora do Carmo", "Recife")
        manual_holidays[date(year, 12, 8)] = ("Nossa Senhora da Conceição", "Recife")
        
        # Data Magna (Garantir 6 de Março)
        manual_holidays[date(year, 3, 6)] = ("Data Magna de Pernambuco", "Pernambuco")
        
        # Outros Feriados/Datas Comemorativas Solicitadas
        manual_holidays[date(year, 8, 11)] = ("Criação dos Cursos Jurídicos", "Brasil") 
        manual_holidays[date(year, 10, 15)] = ("Dia dos Professores", "Brasil")
        manual_holidays[date(year, 10, 28)] = ("Dia do Servidor Público", "Brasil")
        
        # Dia do Comerciário (3ª segunda-feira de outubro)
        oct_1 = date(year, 10, 1)
        first_monday_offset = (7 - oct_1.weekday()) % 7
        first_monday = oct_1 + timedelta(days=first_monday_offset)
        third_monday = first_monday + timedelta(weeks=2)
        manual_holidays[third_monday] = ("Dia do Comerciário", "Recife")

        # Datas Móveis (Baseadas na Páscoa)
        easter_date = easter(year)
        
        # Carnaval e Semana Santa
        # Sábado de Zé Pereira (Carnaval) = Páscoa - 50 dias
        carnaval_sat = easter_date - timedelta(days=50)
        manual_holidays[carnaval_sat] = ("Sábado de Carnaval", "Brasil")
        
        # Domingo de Carnaval = Páscoa - 49 dias
        carnaval_sun = easter_date - timedelta(days=49)
        manual_holidays[carnaval_sun] = ("Domingo de Carnaval", "Brasil")

        # Segunda de Carnaval = Páscoa - 48 dias
        carnaval_mon = easter_date - timedelta(days=48)
        manual_holidays[carnaval_mon] = ("Segunda-feira de Carnaval", "Brasil") 
        
        # Terça de Carnaval = Páscoa - 47 dias
        carnaval_tue = easter_date - timedelta(days=47)
        manual_holidays[carnaval_tue] = ("Terça-feira de Carnaval", "Brasil")
        
        # Quarta-feira de Cinzas = Páscoa - 46 dias
        cinzas = easter_date - timedelta(days=46)
        manual_holidays[cinzas] = ("Quarta-feira de Cinzas", "Brasil")
        
        # Quinta-feira Santa = Páscoa - 3 dias
        quinta_santa = easter_date - timedelta(days=3)
        manual_holidays[quinta_santa] = ("Quinta-feira Santa", "Recife")
        
        # Domingo de Páscoa
        manual_holidays[easter_date] = ("Domingo de Páscoa", "Brasil")
        
        # Corpus Christi (60 dias após a Páscoa)
        corpus_christi = easter_date + timedelta(days=60)
        manual_holidays[corpus_christi] = ("Corpus Christi", "Recife")
        
        # Definir períodos de feriadão fixos (Carnaval e Semana Santa)
        carnaval_dates = {carnaval_sat, carnaval_sun, carnaval_mon, carnaval_tue, cinzas}
        
        # Semana Santa: Quinta até Domingo (Sexta já é feriado, Domingo é Páscoa)
        sexta_santa = easter_date - timedelta(days=2)
        semana_santa_dates = {quinta_santa, sexta_santa, easter_date}
        
        # Unir todas as datas
        all_dates = set(br_holidays.keys()) | set(pe_holidays.keys()) | set(manual_holidays.keys())
        
        sorted_dates = sorted(list(all_dates))
        
        for feriado_date in sorted_dates:
            name = ""
            scope = ""
            
            # Verificar manuais primeiro para garantir override
            if feriado_date in manual_holidays:
                name, scope = manual_holidays[feriado_date]
            else:
                is_national = feriado_date in br_holidays
                is_state = feriado_date in pe_holidays and not is_national
                
                if is_national:
                    scope = "Brasil"
                    name = br_holidays.get(feriado_date)
                elif is_state:
                    scope = "Pernambuco"
                    name = pe_holidays.get(feriado_date)
                else:
                    continue
            
            # Filtrar "Revolução Pernambucana" se não for 6 de março (Data Magna)
            if name == "Revolução Pernambucana" and feriado_date != date(year, 3, 6):
                continue
                
            # Filtrar "Carnaval" genérico da lib holidays se já temos os específicos
            if name == "Carnaval" and feriado_date in manual_holidays:
                 pass
            
            # Filtrar "Quarta-feira de Cinzas" genérico se já temos
            if name == "Quarta-feira de Cinzas" and feriado_date in manual_holidays:
                 pass

            # Lógica de Feriadão
            is_feriadao = "Não"
            weekday = feriado_date.weekday()
            
            # Carnaval ou Semana Santa
            if feriado_date in carnaval_dates or feriado_date in semana_santa_dates:
                is_feriadao = "Sim"
            # Segunda (0) ou Sexta (4)
            elif weekday == 0 or weekday == 4:
                is_feriadao = "Sim"

            all_holidays_list.append({
                "Feriado": name,
                "Data": feriado_date.strftime("%d/%m/%Y"),
                "Dia da Semana": dia_semana_map[weekday],
                "Mês": mes_map[feriado_date.month],
                "Abrangência": scope,
                "Feriadão": is_feriadao,
                "_date_obj": feriado_date
            })
        
    df = pd.DataFrame(all_holidays_list)
    if "_date_obj" in df.columns:
        df = df.drop(columns=["_date_obj"])
        
    return df

def parse_pt_date(date_str):
    """
    Converte datas no formato '8-dez.23-qui.' ou '08-dez.23' para datetime.
    Trata abreviações de meses em português e sufixos de dia da semana.
    """
    if not isinstance(date_str, str):
        return pd.NaT
        
    # Remove espaços
    date_str = date_str.strip()
    
    # Remove sufixo de dia da semana (ex: -qui, -sex, .qui, .sex)
    # A lógica original usava rsplit('-', 1), mas o erro mostra '8-dez.11-qui.'
    # Vamos tentar remover tudo após o último '-' ou '.' se parecer dia da semana
    
    # Mapa de meses
    meses_map = {
        'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04',
        'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08',
        'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
    }
    
    try:
        # Tenta limpar sufixos comuns de dia da semana (3 letras)
        # Ex: .qui., -qui, .qui
        clean_str = date_str
        if len(clean_str) > 4 and clean_str[-1] == '.':
            clean_str = clean_str[:-1] # Remove ponto final
            
        # Se terminar com -ddd ou .ddd (ex: -qui, .qui)
        if len(clean_str) > 4 and (clean_str[-4] == '-' or clean_str[-4] == '.'):
             clean_str = clean_str[:-4]
             
        # Substitui meses
        lower_str = clean_str.lower()
        for pt_mes, num_mes in meses_map.items():
            if pt_mes in lower_str:
                lower_str = lower_str.replace(pt_mes, num_mes)
                break # Assume apenas um mês por string
        
        # Tenta formatos possíveis
        # O formato original era '%d-%m.%y' -> '08-12.23'
        # Se a string original era '8-dez.23-qui.', virou '8-12.23'
        
        formats = [
            '%d-%m.%y',   # 8-12.23
            '%d-%m-%y',   # 8-12-23
            '%d/%m/%y',   # 8/12/23
            '%d-%m.%Y',   # 8-12.2023
            '%d-%m-%Y',   # 8-12-2023
            '%d/%m/%Y'    # 8/12/2023
        ]
        
        for fmt in formats:
            try:
                return pd.to_datetime(lower_str, format=fmt)
            except ValueError:
                continue
                
        # Fallback genérico
        return pd.to_datetime(clean_str, dayfirst=True)
        
    except Exception:
        return pd.NaT

