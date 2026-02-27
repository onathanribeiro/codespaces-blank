import streamlit as st
import pandas as pd
import os
import io
import datetime
from weasyprint import HTML as WeasyHTML
import sqlite3

# --- Configurações Iniciais do Streamlit ---
st.set_page_config(layout="wide", page_title="Consulta e Comparação de Imóveis")

st.title("🏡 Consulta e Comparação de Imóveis")
st.markdown("Use os filtros abaixo para encontrar transações de ITBI e comparar com imóveis de interesse.")

# --- Caminhos dos Arquivos ---
BASE_DIR = os.path.dirname(__file__) 
caminho_itbi_db = os.path.join(BASE_DIR, 'data', 'dados_itbi_unificados.db')
caminho_imoveis_reduzido_db = os.path.join(BASE_DIR, 'data', 'imoveis_sp_reduzido.db')

arquivos_excel = {
    2021: os.path.join(BASE_DIR, 'data', 'GUIAS DE ITBI PAGAS (2021).xlsx'),
    2022: os.path.join(BASE_DIR, 'data', 'GUIAS DE ITBI PAGAS (2022).xlsx'),
    2023: os.path.join(BASE_DIR, 'data', 'GUIAS DE ITBI PAGAS (2023).xlsx'),
    2024: os.path.join(BASE_DIR, 'data', 'GUIAS DE ITBI PAGAS (2024).xlsx'),
    2025: os.path.join(BASE_DIR, 'data', 'GUIAS DE ITBI PAGAS (2025).xlsx'),
}
colunas_desejadas_excel = [
    'Nome do Logradouro', 'Número', 'Complemento',
    'Valor de Transação (declarado pelo contribuinte)',
    'Data de Transação', 'Área Construída (m2)',
    'Proporção Transmitida (%)'
]
abas_para_ignorar = ['LEGENDA', 'EXPLICAÇÕES', 'Tabela de USOS', 'Tabela de PADRÕES']

# --- Funções de Carregamento e Processamento ---

@st.cache_data
def carregar_planilhas_excel(caminho_arquivo, colunas, abas_ignorar):
    try:
        todas_abas = pd.read_excel(caminho_arquivo, sheet_name=None)
        planilhas_validas = []
        for nome_aba, df in todas_abas.items():
            if nome_aba in abas_ignorar: continue
            if set(colunas).issubset(df.columns):
                planilhas_validas.append(df[colunas])
        return pd.concat(planilhas_validas, ignore_index=True) if planilhas_validas else pd.DataFrame(columns=colunas)
    except: return pd.DataFrame(columns=colunas)

@st.cache_data
def carregar_e_processar_dados_itbi():
    dados_carregados = pd.DataFrame()
    if os.path.exists(caminho_itbi_db):
        try:
            conn = sqlite3.connect(caminho_itbi_db)
            dados_carregados = pd.read_sql_query("SELECT * FROM itbi_data", conn)
            conn.close()
            st.success("Dados de ITBI carregados a partir do arquivo .db!")
        except: pass
    
    if dados_carregados.empty: 
        lista_dfs = []
        for ano, caminho_arquivo in arquivos_excel.items():
            if os.path.exists(caminho_arquivo):
                df_ano = carregar_planilhas_excel(caminho_arquivo, colunas_desejadas_excel, abas_para_ignorar)
                if not df_ano.empty: lista_dfs.append(df_ano)

        if lista_dfs:
            dados_carregados = pd.concat(lista_dfs, ignore_index=True)
            dados_carregados['Nome do Logradouro'] = dados_carregados['Nome do Logradouro'].astype(str).str.upper()
            dados_carregados['Proporção Transmitida (%)'] = pd.to_numeric(dados_carregados['Proporção Transmitida (%)'], errors='coerce')
            dados_carregados = dados_carregados[dados_carregados['Proporção Transmitida (%)'] == 100].copy()
            dados_carregados['Data de Transação'] = pd.to_datetime(dados_carregados['Data de Transação'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
            try:
                os.makedirs(os.path.dirname(caminho_itbi_db), exist_ok=True)
                conn = sqlite3.connect(caminho_itbi_db)
                dados_carregados.to_sql('itbi_data', conn, if_exists='replace', index=False)
                conn.close()
            except: pass

    if not dados_carregados.empty:
        dados_processados = dados_carregados.copy()
        dados_processados['Número'] = pd.to_numeric(dados_processados['Número'], errors='coerce').fillna(0).astype(int)
        dados_processados['Valor de Transação (declarado pelo contribuinte)'] = pd.to_numeric(dados_processados['Valor de Transação (declarado pelo contribuinte)'], errors='coerce')
        dados_processados['Área Construída (m2)'] = pd.to_numeric(dados_processados['Área Construída (m2)'], errors='coerce')
        dados_processados['Valor por m²'] = dados_processados.apply(lambda row: row['Valor de Transação (declarado pelo contribuinte)'] / row['Área Construída (m2)'] if row['Área Construída (m2)'] > 0 else 0, axis=1)
        dados_processados['Data de Transação Original'] = pd.to_datetime(dados_processados['Data de Transação'], errors='coerce')
        dados_processados['Data de Transação'] = dados_processados['Data de Transação Original'].dt.strftime('%d/%m/%Y').fillna('')
        return dados_processados
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def buscar_opcoes_imoveis_por_endereco(logradouro_input, numero_input, complemento_input=""):
    if not os.path.exists(caminho_imoveis_reduzido_db): return []
    try:
        conn = sqlite3.connect(caminho_imoveis_reduzido_db)
        cursor = conn.cursor()
        t_log = logradouro_input.upper().strip()
        t_num = int(numero_input)
        t_compl = complemento_input.upper().strip() if complemento_input else ""
        
        query = "SELECT complemento_imovel, area_construida FROM imoveis_sp WHERE logradouro_nome LIKE ? AND numero_imovel = ?"
        params = [f"%{t_log}%", t_num]
        if t_compl:
            query += " AND complemento_imovel LIKE ?"
            params.append(f"%{t_compl}%")
        
        cursor.execute(query, params)
        res = cursor.fetchall()
        conn.close()
        return res
    except: return []

# --- Inicialização ---
dados_itbi = carregar_e_processar_dados_itbi()
colunas_base_exibicao = ['Nome do Logradouro', 'Número', 'Complemento', 'Valor de Transação (declarado pelo contribuinte)', 'Data de Transação', 'Área Construída (m2)', 'Valor por m²']

# --- Filtros ITBI ---
st.header("🔍 Critérios de Busca (Dados de ITBI)")
col_cb1, col_cb2 = st.columns(2)
with col_cb1: busca_range = st.checkbox("Buscar por range de número?", key="chk_range")
with col_cb2: filtrar_area = st.checkbox("Filtrar por Área Construída (m²)?", key="chk_area")

with st.form("busca_form"):
    nome_ruas = st.text_area("Nome das Ruas:", key="nome_rua_input").upper()
    c_n1, c_n2 = st.columns(2)
    with c_n1:
        if busca_range: n_min = st.number_input("Número Mínimo:", value=0)
        else: n_exato = st.number_input("Número Exato:", value=0)
    with c_n2:
        if busca_range: n_max = st.number_input("Número Máximo:", value=10000)
    
    if filtrar_area:
        ca1, ca2 = st.columns(2)
        with ca1: a_min = st.number_input("Área Mínima (m²):", value=0.0)
        with ca2: a_max = st.number_input("Área Máxima (m²):", value=5000.0)
    
    btn_itbi = st.form_submit_button("Consultar ITBI")

if btn_itbi:
    if not dados_itbi.empty:
        df_f = dados_itbi.copy()
        l_ruas = [r.strip().upper() for r in nome_ruas.split('\n') if r.strip()]
        if l_ruas:
            df_f = df_f[df_f['Nome do Logradouro'].str.contains('|'.join(l_ruas), na=False, case=False)]
        if busca_range:
            df_f = df_f[(df_f['Número'] >= n_min) & (df_f['Número'] <= n_max)]
        elif n_exato > 0:
            df_f = df_f[df_f['Número'] == n_exato]
        if filtrar_area:
            df_f = df_f[(df_f['Área Construída (m2)'] >= a_min) & (df_f['Área Construída (m2)'] <= a_max)]
        
        if not df_f.empty:
            st.session_state.resultado_consulta_itbi = df_f.reset_index(drop=True)
            df_vis = st.session_state.resultado_consulta_itbi[colunas_base_exibicao].copy()
            df_vis['Valor de Transação (declarado pelo contribuinte)'] = df_vis['Valor de Transação (declarado pelo contribuinte)'].map('R$ {:,.2f}'.format)
            df_vis['Valor por m²'] = df_vis['Valor por m²'].map('R$ {:,.2f}'.format)
            df_vis['Selecionar'] = False
            st.session_state.df_formatado_itbi = df_vis[['Selecionar'] + colunas_base_exibicao]
        else:
            st.warning("Nenhum dado encontrado.")
            st.session_state.df_formatado_itbi = pd.DataFrame()

# --- Tabela e Médias ---
if 'df_formatado_itbi' in st.session_state and not st.session_state.df_formatado_itbi.empty:
    st.subheader("Resultados Detalhados")
    edit_itbi = st.data_editor(st.session_state.df_formatado_itbi, use_container_width=True, hide_index=True, key="ed_itbi")
    sel_itbi = edit_itbi[edit_itbi["Selecionar"]]
    
    if not sel_itbi.empty:
        df_orig = st.session_state.resultado_consulta_itbi.loc[sel_itbi.index]
        media_val = df_orig['Valor de Transação (declarado pelo contribuinte)'].mean()
        media_m2 = df_orig['Valor por m²'].mean()
        
        st.session_state['sel_pdf_data'] = sel_itbi.drop(columns=['Selecionar'])
        st.session_state['media_val_pdf'] = media_val
        st.session_state['media_m2_pdf'] = media_m2
        
        st.info(f"**Média Selecionada ({len(sel_itbi)} itens):** R$ {media_m2:,.2f} / m²")

# --- Comparador ---
st.header("⚖️ Comparação de Imóveis")
c1, c2, c3 = st.columns(3)
with c1: log_c = st.text_input("Logradouro:", key="l_c").upper()
with c2: num_c = st.number_input("Número:", value=0, key="n_c")
with c3: com_c = st.text_input("Complemento (opcional):", key="c_c").upper()

if st.button("Buscar Área do Imóvel"):
    if log_c and num_c > 0:
        ops = buscar_opcoes_imoveis_por_endereco(log_c, num_c, com_c)
        if ops:
            st.session_state.ops_imv = ops
            st.success(f"Encontradas {len(ops)} unidades.")
        else:
            st.warning("Não encontrado.")
            st.session_state.ops_imv = []

if st.session_state.get('ops_imv'):
    l_str = [f"Unidade: {o[0]} | Área: {o[1]:,.2f} m²" for o in st.session_state.ops_imv]
    escolha = st.selectbox("Selecione a unidade correta:", l_str)
    d_sel = st.session_state.ops_imv[l_str.index(escolha)]
    st.session_state['area_comp'] = float(d_sel[1])
    st.session_state['detalhes_comp'] = {'log': log_c, 'num': num_c, 'compl': d_sel[0], 'area': float(d_sel[1])}

area_atual = st.session_state.get('area_comp', 0.0)
st.markdown(f"**Área Construída:** `{area_atual:,.2f}` m²")

if st.button("Calcular e Gerar Relatório"):
    m2_ref = st.session_state.get('media_m2_pdf', 0.0)
    if m2_ref > 0 and area_atual > 0:
        val_est = area_atual * m2_ref
        st.metric("VALOR TOTAL ESTIMADO", f"R$ {val_est:,.2f}")
        
        # --- Geração de PDF Robusta (Template Original) ---
        df_pdf = st.session_state.get('sel_pdf_data', pd.DataFrame())
        tab_html = df_pdf.to_html(index=False, classes='dataframe')
        det = st.session_state['detalhes_comp']
        
        html_doc = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #333; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #eee; }}
                h2 {{ color: #2980b9; margin-top: 20px; border-bottom: 1px solid #eee; }}
                .highlight {{ background: #f8f9fa; padding: 15px; border-left: 5px solid #2980b9; margin: 15px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 9pt; }}
                th {{ background: #f2f2f2; font-weight: bold; }}
                .footer {{ margin-top: 30px; font-size: 8pt; color: #777; }}
            </style>
        </head>
        <body>
            <h1>Relatório de Consulta e Comparação de ITBI</h1>
            <p>Gerado em: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
            
            <h2>Estatísticas da Amostra Selecionada</h2>
            <div class="highlight">
                <p><b>Número de Imóveis Comparados:</b> {len(df_pdf)}</p>
                <p><b>Média do Valor de Transação:</b> R$ {st.session_state['media_val_pdf']:,.2f}</p>
                <p><b>Média do Valor por m² (Referência):</b> R$ {m2_ref:,.2f}</p>
            </div>

            <h2>Dados Detalhados dos Itens Selecionados</h2>
            {tab_html}

            <h2>Imóvel Avaliado</h2>
            <div class="highlight" style="border-left-color: #27ae60; background: #f0fff4;">
                <p><b>Endereço:</b> {det['log']}, {det['num']} - {det['compl']}</p>
                <p><b>Área Construída:</b> {det['area']:,.2f} m²</p>
                <p><b>Valor por m² Aplicado:</b> R$ {m2_ref:,.2f}</p>
                <h3 style="margin: 10px 0 0 0;">VALOR TOTAL ESTIMADO: R$ {val_est:,.2f}</h3>
            </div>
            
            <div class="footer">Relatório gerado automaticamente via Sistema de Consulta de ITBI.</div>
        </body>
        </html>
        """
        pdf_bytes = WeasyHTML(string=html_doc).write_pdf()
        st.download_button("📥 Baixar Relatório PDF Completo", data=pdf_bytes, file_name="relatorio_itbi_completo.pdf", mime="application/pdf")
    else:
        st.error("Selecione os imóveis de ITBI e a unidade de comparação primeiro.")