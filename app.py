import time
import streamlit as st
import pandas as pd
import plotly.express as px  # Importação faltante adicionada
import re
from datetime import datetime, timedelta

# ================================================
# MÓDULO 1: CONFIGURAÇÕES E CONSTANTES
# ================================================
ELAPSED_TIME = 30
REFRESH_INTERVAL = 0.3
MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 
        'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

# ================================================
# MÓDULO 2: FUNÇÕES DE INTERFACE
# ================================================
def criar_relogio(tempo_restante, tempo_total):
    """Cria um relógio de contagem regressiva com redução visual correta"""
    progresso = 360 * (tempo_restante / tempo_total)
    return f"""
    <style>
    .relogio {{
        width: 100px;
        height: 100px;
        border-radius: 50%;
        background: 
            conic-gradient(#1f77b4 {progresso}deg, #f0f2f6 0deg);
        position: relative;
        margin: 20px auto;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    
    .contador {{
        font-family: monospace;
        font-size: 1.5rem;
        font-weight: bold;
        color: #1f77b4;
        z-index: 2;
    }}
    
    .relogio::before {{
        content: '';
        position: absolute;
        width: 80%;
        height: 80%;
        background: white;
        border-radius: 50%;
    }}
    </style>
    
    <div class="relogio">
        <div class="contador">{int(tempo_restante)}</div>
    </div>
    """

# ================================================
# MÓDULO 3: PROCESSAMENTO DE DADOS
# ================================================
def parse_oracle_log(uploaded_file):
    """Processa arquivo de log Oracle"""
    pattern = r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(ORA-\d{5}):\s+(?P<message>.+)'
    entries = []
    
    try:
        content = uploaded_file.getvalue().decode('utf-8')
        for line in content.split('\n'):
            match = re.search(pattern, line)
            if match:
                dt = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                entries.append({
                    'timestamp': dt,
                    'error_code': match.group(2),
                    'error_message': match.group(3).strip()
                })
        return pd.DataFrame(entries)
    except Exception as e:
        st.error(f"Erro no parsing: {str(e)}")
        return pd.DataFrame()

def prepare_data(df):
    """Prepara dados temporais em português"""
    if not df.empty:
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            df['year'] = df['timestamp'].dt.year
            df['mês'] = df['timestamp'].dt.month.apply(lambda x: MESES[x-1])
            return df
        except KeyError:
            st.error("Coluna 'timestamp' não encontrada")
            return pd.DataFrame()
    return df

# ================================================
# MÓDULO 4: GERENCIAMENTO DE ESTADO
# ================================================
def init_state():
    """Inicializa o estado da sessão"""
    if 'car' not in st.session_state:
        st.session_state.car = {
            'view_index': 0,
            'last_update': time.time(),
            'raw_data': None,
            'cutoff_date': None
        }

# ================================================
# MÓDULO 5: RENDERIZAÇÃO DE CONTEÚDO
# ================================================
def render_content(data, view_config, top_k):
    """Renderiza gráficos e tabelas"""
    try:
        if view_config['type'] == 'chart':
            # Cálculos dos dados
            if view_config['group'] == 'date':
                grouped = data.groupby('date').size().reset_index(name='total')
                x_col = 'date'
            elif view_config['group'] == 'year':
                grouped = data.groupby('year').size().reset_index(name='total')
                x_col = 'year'
            elif view_config['group'] == 'mês':
                grouped = data.groupby('mês').size().reset_index(name='total')
                x_col = 'mês'
            elif view_config['group'] == 'error_code':
                grouped = data.groupby('error_code').size().reset_index(name='total')
                x_col = 'error_code'
            
            # Criação do gráfico com Plotly
            if view_config['chart'] == 'bar':
                fig = px.bar(grouped, x=x_col, y='total', title=view_config['title'])
            elif view_config['chart'] == 'line':
                fig = px.line(grouped, x=x_col, y='total', title=view_config['title'], markers=True)
            
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
            
        elif view_config['type'] == 'table':
            top_data = data.groupby('error_code', as_index=False)\
                           .agg(
                               total=('error_code', 'size'),
                               descricao=('error_message', lambda x: x.mode()[0])
                           )\
                           .sort_values('total', ascending=False)\
                           .head(top_k)
            
            st.markdown(f"### {view_config['title']}")
            st.dataframe(
                top_data,
                column_config={
                    "error_code": "Código",
                    "descricao": "Descrição Mais Frequente",
                    "total": "Ocorrências"
                },
                hide_index=True,
                use_container_width=True
            )
            
    except Exception as e:
        st.error(f"Erro na renderização: {str(e)}")

# ================================================
# MÓDULO 6: FUNÇÃO PRINCIPAL
# ================================================
def main():
    st.set_page_config("Oracle Analytics", layout="wide")
    init_state()
    
    # Configurações na sidebar
    with st.sidebar:
        st.header("⚙️ Controles")
        rotate_time = st.slider("Tempo por dashboard (s)", 10, 300, 30)
        refresh_interval = st.slider("Atualização (s)", 0.1, 1.0, 0.3)
        top_k = st.number_input("Top erros (K)", 1, 50, 10)
    
    # Upload de arquivo
    uploaded_file = st.file_uploader("Carregue seu log Oracle", type=['log','txt'])
    
    # Container principal
    main_placeholder = st.empty()
    
    if uploaded_file:
        if st.session_state.car['raw_data'] is None:
            with st.spinner("Processando arquivo..."):
                df = prepare_data(parse_oracle_log(uploaded_file))
                if not df.empty:
                    st.session_state.car.update({
                        'raw_data': df,
                        'cutoff_date': (datetime.now() - timedelta(days=30)).date()
                    })

        if st.session_state.car['raw_data'] is not None:
            current_time = time.time()
            elapsed = current_time - st.session_state.car['last_update']
            tempo_restante = max(0, rotate_time - elapsed)
            
            # Rotação automática
            if elapsed >= rotate_time:
                st.session_state.car['view_index'] = (st.session_state.car['view_index'] + 1) % 10
                st.session_state.car['last_update'] = current_time
                st.rerun()
            
            # Lista de visualizações
            views = [
                {'type': 'chart', 'filter': lambda d: d[d['date'] >= st.session_state.car['cutoff_date']], 
                 'title': "1. Últimos 30 Dias (Linear)", 'chart': 'line', 'group': 'date'},
                {'type': 'chart', 'filter': lambda d: d[d['date'] >= st.session_state.car['cutoff_date']], 
                 'title': "2. Últimos 30 Dias (Barras)", 'chart': 'bar', 'group': 'date'},
                {'type': 'chart', 'filter': lambda d: d, 
                 'title': "3. Histórico Anual (Linear)", 'chart': 'line', 'group': 'year'},
                {'type': 'chart', 'filter': lambda d: d, 
                 'title': "4. Histórico Mensal (Linear)", 'chart': 'line', 'group': 'mês'},
                {'type': 'chart', 'filter': lambda d: d, 
                 'title': "5. Histórico Anual (Barras)", 'chart': 'bar', 'group': 'year'},
                {'type': 'chart', 'filter': lambda d: d, 
                 'title': "6. Histórico Mensal (Barras)", 'chart': 'bar', 'group': 'mês'},
                {'type': 'chart', 'filter': lambda d: d[d['date'] >= st.session_state.car['cutoff_date']], 
                 'title': "7. Erros Recentes (Top)", 'chart': 'bar', 'group': 'error_code'},
                {'type': 'chart', 'filter': lambda d: d, 
                 'title': "8. Erros Históricos (Top)", 'chart': 'bar', 'group': 'error_code'},
                {'type': 'table', 'filter': lambda d: d[d['date'] >= st.session_state.car['cutoff_date']], 
                 'title': f"9. Top {top_k} Erros Recentes"},
                {'type': 'table', 'filter': lambda d: d, 
                 'title': f"10. Top {top_k} Erros Históricos"}
            ]
            
            # Renderização do conteúdo
            with main_placeholder.container():
                current_view = views[st.session_state.car['view_index']]
                filtered_data = current_view['filter'](st.session_state.car['raw_data'])
                render_content(filtered_data, current_view, top_k)
                
                # Relógio de contagem regressiva
                st.markdown(
                    criar_relogio(tempo_restante, rotate_time), 
                    unsafe_allow_html=True
                )
            
            # Atualização do ciclo
            time.sleep(refresh_interval)
            st.rerun()

if __name__ == "__main__":
    main()