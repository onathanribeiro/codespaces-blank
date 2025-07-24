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

# Caminho para o arquivo SQLite dos dados do ITBI
caminho_itbi_db = os.path.join(BASE_DIR, 'data', 'dados_itbi_unificados.db')

# Caminho para o arquivo SQLite dos dados de imóveis (o reduzido)
caminho_imoveis_reduzido_db = os.path.join(BASE_DIR, 'data', 'imoveis_sp_reduzido.db')


# Configurações para carregar arquivos Excel (mantidas por compatibilidade, mas o foco é o DB)
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

# --- Função para Carregar Planilhas (mantém-se a mesma) ---
@st.cache_data
def carregar_planilhas_excel(caminho_arquivo, colunas, abas_ignorar):
    """Carrega dados de um arquivo Excel, filtrando abas e colunas."""
    try:
        todas_abas = pd.read_excel(caminho_arquivo, sheet_name=None)
        planilhas_validas = []
        for nome_aba, df in todas_abas.items():
            if nome_aba in abas_ignorar:
                continue
            if set(colunas).issubset(df.columns):
                planilhas_validas.append(df[colunas])
            else:
                st.warning(f"Aba '{nome_aba}' em '{os.path.basename(caminho_arquivo)}' ignorada: faltam colunas essenciais.")
        if planilhas_validas:
            return pd.concat(planilhas_validas, ignore_index=True)
        return pd.DataFrame(columns=colunas)
    except FileNotFoundError:
        st.error(f"Erro: Arquivo não encontrado em '{caminho_arquivo}'.")
        return pd.DataFrame(columns=colunas)
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo Excel '{caminho_arquivo}': {e}")
        return pd.DataFrame(columns=colunas)

# --- Função Principal de Carregamento e Processamento de Dados de ITBI ---
@st.cache_data
def carregar_e_processar_dados_itbi():
    """Carrega dados de ITBI de DB ou Excel e os pré-processa."""
    dados_carregados = pd.DataFrame()
    
    # Tenta carregar do SQLite DB primeiro
    if os.path.exists(caminho_itbi_db):
        try:
            conn = sqlite3.connect(caminho_itbi_db)
            dados_carregados = pd.read_sql_query("SELECT * FROM itbi_data", conn)
            conn.close()
            st.success("Dados de ITBI carregados a partir do arquivo .db!")
        except Exception as e:
            st.warning(f"Erro ao carregar DB de ITBI: {e}. Tentando carregar do Excel.")
    
    # Se o DB não carregou ou deu erro, OU SEJA, se dados_carregados ainda está vazio, carrega do Excel
    if dados_carregados.empty: 
        st.info("Arquivo .db de ITBI não encontrado ou com erro. Carregando as planilhas do Excel...")
        lista_dfs = []
        for ano, caminho_arquivo in arquivos_excel.items():
            if os.path.exists(caminho_arquivo):
                df_ano = carregar_planilhas_excel(caminho_arquivo, colunas_desejadas_excel, abas_para_ignorar)
                if not df_ano.empty:
                    lista_dfs.append(df_ano)
            else:
                st.warning(f"Aviso: Arquivo do ano {ano} não encontrado em {caminho_arquivo}. Verifique o caminho.")

        if lista_dfs:
            dados_carregados = pd.concat(lista_dfs, ignore_index=True)
            if not dados_carregados.empty:
                # --- PRÉ-PROCESSAMENTO ANTES DE SALVAR NO DB ---
                dados_carregados['Nome do Logradouro'] = dados_carregados['Nome do Logradouro'].astype(str).str.upper()
                
                dados_carregados['Proporção Transmitida (%)'] = pd.to_numeric(
                    dados_carregados['Proporção Transmitida (%)'], errors='coerce'
                )
                dados_carregados = dados_carregados[
                    dados_carregados['Proporção Transmitida (%)'] == 100
                ].copy()
                
                dados_carregados['Data de Transação'] = pd.to_datetime(dados_carregados['Data de Transação'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
                if 'Data de Transação Original' in dados_carregados.columns:
                    dados_carregados = dados_carregados.drop(columns=['Data de Transação Original'])

                try:
                    os.makedirs(os.path.dirname(caminho_itbi_db), exist_ok=True)
                    conn = sqlite3.connect(caminho_itbi_db)
                    dados_carregados.to_sql('itbi_data', conn, if_exists='replace', index=False)
                    conn.close()
                    st.success("Dados de ITBI carregados do Excel, processados e salvos no formato .db!")
                except Exception as e:
                    st.warning(f"Não foi possível salvar o DB de ITBI em {caminho_itbi_db}: {e}. O app continuará com os dados em memória.")
            else: 
                st.error("Nenhum arquivo Excel válido encontrado ou carregado para ITBI. O DataFrame de dados está vazio.")
        else:
            st.error("Não foi possível carregar dados de ITBI do Excel. Verifique os caminhos e permissões.")
    
    # --- PÓS-PROCESSAMENTO FINAL DO ITBI ---
    if not dados_carregados.empty:
        dados_processados = dados_carregados.copy()
        
        dados_processados['Proporção Transmitida (%)'] = pd.to_numeric(
            dados_processados['Proporção Transmitida (%)'], errors='coerce'
        )
        dados_processados = dados_processados[
            dados_processados['Proporção Transmitida (%)'] == 100
        ].copy()

        dados_processados['Número'] = pd.to_numeric(dados_processados['Número'], errors='coerce')
        dados_processados = dados_processados.dropna(subset=['Número']).copy()
        dados_processados['Número'] = dados_processados['Número'].astype(int)
        
        dados_processados['Valor de Transação (declarado pelo contribuinte)'] = pd.to_numeric(dados_processados['Valor de Transação (declarado pelo contribuinte)'], errors='coerce')
        dados_processados['Área Construída (m2)'] = pd.to_numeric(dados_processados['Área Construída (m2)'], errors='coerce')
        
        dados_processados['Valor por m²'] = dados_processados.apply(
            lambda row: row['Valor de Transação (declarado pelo contribuinte)'] / row['Área Construída (m2)'] if row['Área Construída (m2)'] > 0 else 0,
            axis=1
        )
        dados_processados['Valor por m²'] = dados_processados['Valor por m²'].fillna(0)
        
        dados_processados['Data de Transação Original'] = pd.to_datetime(dados_processados['Data de Transação'], errors='coerce')
        dados_processados['Data de Transação'] = dados_processados['Data de Transação Original'].dt.strftime('%d/%m/%Y').fillna('')

        return dados_processados
    else: 
        return pd.DataFrame()

# NOVO: Função para buscar área construída no imoveis_sp_reduzido.db por logradouro, número e complemento
@st.cache_data(ttl=3600) # Cacheia a conexão e o resultado por 1 hora
def buscar_area_por_detalhes_endereco(logradouro_input, numero_input, complemento_input=""):
    """
    Busca a área construída no imoveis_sp_reduzido.db com base no logradouro, número e complemento.
    Retorna a área ou None se não encontrada.
    """
    if not os.path.exists(caminho_imoveis_reduzido_db):
        st.warning(f"Arquivo '{os.path.basename(caminho_imoveis_reduzido_db)}' não encontrado na pasta 'data/'. A busca por endereço não está disponível.")
        return None

    try:
        conn = sqlite3.connect(caminho_imoveis_reduzido_db)
        cursor = conn.cursor()
        
        # Prepara os termos de busca, convertendo para maiúsculas e removendo espaços extras
        termo_logradouro = logradouro_input.upper().strip()
        termo_numero = int(numero_input) # Número deve ser exato
        termo_complemento = complemento_input.upper().strip() if complemento_input else ""

        # Construir a query SQL dinamicamente
        query = "SELECT area_construida FROM imoveis_sp WHERE logradouro_nome LIKE ?"
        params = [f"%{termo_logradouro}%"] # Busca parcial no logradouro

        # Adicionar número se fornecido
        if termo_numero > 0:
            query += " AND numero_imovel = ?"
            params.append(termo_numero)
        
        # Adicionar complemento se fornecido
        if termo_complemento:
            query += " AND complemento_imovel LIKE ?"
            params.append(f"%{termo_complemento}%") # Busca parcial no complemento
        
        query += " LIMIT 1" # Limita a 1 resultado para pegar a primeira correspondência

        cursor.execute(query, params)
        resultado = cursor.fetchone()
        
        conn.close()
        
        if resultado:
            area = float(resultado[0]) # Converte para float
            return area
        else:
            return None
    except Exception as e:
        st.error(f"Erro ao buscar área no 'imoveis_sp_reduzido.db': {e}")
        return None

# Carrega os dados de ITBI no início
dados_itbi = carregar_e_processar_dados_itbi()

# Definir as colunas base para exibir
colunas_base_exibicao = [
    'Nome do Logradouro', 'Número', 'Complemento',
    'Valor de Transação (declarado pelo contribuinte)',
    'Data de Transação', 'Área Construída (m2)', 'Valor por m²'
]

# --- Interface de Busca (Streamlit) ---
st.header("🔍 Critérios de Busca (Dados de ITBI)")

col_dynamic_checkbox1, col_dynamic_checkbox2 = st.columns(2)
with col_dynamic_checkbox1:
    busca_range = st.checkbox("Buscar por range de número?", key="busca_range_dynamic_checkbox")
with col_dynamic_checkbox2:
    filtrar_area = st.checkbox("Filtrar por Área Construída (m²)?", key="filtrar_area_dynamic_checkbox")

with st.form("busca_form"):
    nome_rua = st.text_input("Nome da Rua:", help="Parte ou nome completo da rua.", key="nome_rua_input").upper()

    col_num1, col_num2 = st.columns(2)
    with col_num1:
        if busca_range:
            num_min = st.number_input("Número Mínimo:", min_value=0, value=st.session_state.get('num_min_input', 0), step=1, key="num_min_form")
        else:
            num_exato = st.number_input("Número Exato:", min_value=0, value=st.session_state.get('num_exato_input', 0), step=1, key="num_exato_form")
    with col_num2:
        if busca_range:
            num_max = st.number_input("Número Máximo:", min_value=0, value=st.session_state.get('num_max', 10000), step=1, key="num_max_form")
    
    if filtrar_area:
        col_area1, col_area2 = st.columns(2)
        with col_area1:
            area_min = st.number_input("Área Mínima (m²):", min_value=0.0, value=st.session_state.get('area_min', 0.0), step=1.0, key="area_min_form")
        with col_area2:
            area_max = st.number_input("Área Máxima (m²):", min_value=0.0, value=st.session_state.get('area_max', 5000.0), step=1.0, key="area_max_form")
    
    submitted = st.form_submit_button("Consultar ITBI")

# --- Lógica de Consulta e Exibição de Resultados do ITBI ---
if submitted:
    if dados_itbi.empty:
        st.error("Não há dados de ITBI carregados para realizar a consulta. Verifique os caminhos dos arquivos e o carregamento inicial.")
        st.session_state.resultado_consulta_itbi = pd.DataFrame()
        st.session_state.df_para_exibir_formatado_itbi = pd.DataFrame()
    else:
        st.subheader("📊 Resultados da Consulta de ITBI")
        
        df_filtrado_itbi = dados_itbi.copy()
        
        nome_rua_valor = st.session_state.get('nome_rua_input', '')
        if nome_rua_valor:
            df_filtrado_itbi = df_filtrado_itbi[df_filtrado_itbi['Nome do Logradouro'].str.contains(nome_rua_valor, case=False, na=False)]

        if st.session_state.get('busca_range_dynamic_checkbox', False):
            min_val = st.session_state.get('num_min_form', 0)
            max_val = st.session_state.get('num_max_form', 10000)
            df_filtrado_itbi = df_filtrado_itbi[(df_filtrado_itbi['Número'] >= min_val) & (df_filtrado_itbi['Número'] <= max_val)]
        else:
            exact_val = st.session_state.get('num_exato_form', 0)
            df_filtrado_itbi = df_filtrado_itbi[df_filtrado_itbi['Número'] == exact_val]

        if st.session_state.get('filtrar_area_dynamic_checkbox', False):
            min_area = st.session_state.get('area_min_form', 0.0)
            max_area = st.session_state.get('area_max_form', 5000.0)
            df_filtrado_itbi = df_filtrado_itbi[(df_filtrado_itbi['Área Construída (m2)'] >= min_area) & (df_filtrado_itbi['Área Construída (m2)'] <= max_area)]

        if df_filtrado_itbi.empty:
            st.warning("Nenhum resultado de ITBI encontrado com os critérios de busca especificados.")
            st.session_state.resultado_consulta_itbi = pd.DataFrame()
            st.session_state.df_para_exibir_formatado_itbi = pd.DataFrame()
        else:
            st.session_state.resultado_consulta_itbi = df_filtrado_itbi.reset_index(drop=True)

            colunas_para_exibir_final = colunas_base_exibicao[:]
            if 'Complemento' in st.session_state.resultado_consulta_itbi.columns and st.session_state.resultado_consulta_itbi['Complemento'].isnull().all():
                colunas_para_exibir_final.remove('Complemento')

            df_para_exibir_raw = st.session_state.resultado_consulta_itbi[[col for col in colunas_para_exibir_final if col in st.session_state.resultado_consulta_itbi.columns]].copy()
            
            df_para_exibir_formatado_itbi = df_para_exibir_raw.copy()
            df_para_exibir_formatado_itbi['Valor de Transação (declarado pelo contribuinte)'] = df_para_exibir_formatado_itbi['Valor de Transação (declarado pelo contribuinte)'].map('R$ {:,.2f}'.format)
            df_para_exibir_formatado_itbi['Valor por m²'] = df_para_exibir_formatado_itbi['Valor por m²'].map('R$ {:,.2f}'.format)
            
            # Adicionar a coluna 'Selecionar' e REORDENAR
            df_para_exibir_formatado_itbi['Selecionar'] = False
            cols_ordered = ['Selecionar'] + [col for col in df_para_exibir_formatado_itbi.columns if col != 'Selecionar']
            df_para_exibir_formatado_itbi = df_para_exibir_formatado_itbi[cols_ordered]

            st.session_state.df_para_exibir_formatado_itbi = df_para_exibir_formatado_itbi

# --- Exibição da Tabela de ITBI (Fora do bloco 'if submitted' para que persista) ---
if 'df_para_exibir_formatado_itbi' in st.session_state and not st.session_state.df_para_exibir_formatado_itbi.empty:
    st.subheader("Resultados Detalhados do ITBI (Selecione para o PDF ou Comparação)")

    edited_df_itbi = st.data_editor(
        st.session_state.df_para_exibir_formatado_itbi,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(
                "Gerar PDF / Comparar",
                help="Selecione as linhas para gerar PDFs individuais ou para usar na comparação",
                default=False,
            )
        },
        key="data_editor_results_itbi"
    )
    
    selected_rows_for_action_itbi = edited_df_itbi[edited_df_itbi["Selecionar"]]

    st.subheader("Sumário e Ações de ITBI")

    if not selected_rows_for_action_itbi.empty:
        selected_indices_original_itbi = selected_rows_for_action_itbi.index
        df_selecionado_original_itbi = st.session_state.resultado_consulta_itbi.loc[selected_indices_original_itbi]

        media_valor_selecionado_itbi = df_selecionado_original_itbi['Valor de Transação (declarado pelo contribuinte)'].mean()
        media_valor_m2_selecionado_itbi = df_selecionado_original_itbi['Valor por m²'].mean()

        st.info(f"**Média dos Itens SELECIONADOS ({len(selected_rows_for_action_itbi)} imóveis de ITBI):**")
        col_stats_sel1, col_stats_sel2 = st.columns(2)
        with col_stats_sel1:
            st.metric(label="Valor de Transação (Selecionados)", value=f"R$ {media_valor_selecionado_itbi:,.2f}")
        with col_stats_sel2:
            st.metric(label="Valor por m² (Selecionados)", value=f"R$ {media_valor_m2_selecionado_itbi:,.2f}")

        st.markdown("---") 

        # --- Geração de PDF (mantida) ---
        df_para_pdf_final = selected_rows_for_action_itbi.copy()
        if 'Selecionar' in df_para_pdf_final.columns:
            df_para_pdf_final = df_para_pdf_final.drop(columns=['Selecionar'])

        cols_to_use_in_pdf = colunas_base_exibicao[:]
        if 'Complemento' in df_para_pdf_final.columns and df_para_pdf_final['Complemento'].isnull().all():
             cols_to_use_in_pdf.remove('Complemento')

        df_para_pdf_final = df_para_pdf_final[[col for col in cols_to_use_in_pdf if col in df_para_pdf_final.columns]].copy()

        tabela_html = df_para_pdf_final.to_html(index=False, classes='dataframe', escape=False)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Relatório de Consulta ITBI - Itens Selecionados</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; font-size: 10pt; }}
                h1 {{ color: #333; font-size: 18pt; }}
                h2 {{ color: #555; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 20px; font-size: 14pt; }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                    table-layout: fixed; 
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 6px; 
                    text-align: left;
                    word-wrap: break-word; 
                    overflow-wrap: break-word; 
                    font-size: 9pt; 
                }}
                th {{ background-color: #f2f2f2; }}
                .highlight {{ background-color: #e0f2f7; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
                .section-header {{ font-weight: bold; margin-top: 15px; }}
                p {{ font-size: 10pt; }} 
            </style>
        </head>
        <body>
            <h1>Relatório de Consulta de ITBI</h1>
            <p><strong>Data da Geração:</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>

            <h2>Parâmetros da Consulta</h2>
            <p><strong>Nome da Rua Pesquisada:</strong> {st.session_state.get('nome_rua_input', 'N/A').upper()}</p>
            <p><strong>Número da Busca:</strong> {"De " + str(st.session_state.get('num_min_form', 0)) + " a " + str(st.session_state.get('num_max_form', 10000)) if st.session_state.get('busca_range_dynamic_checkbox', False) else "Exato: " + str(st.session_state.get('num_exato_form', 0))}</p>
            {"<p><strong>Área Construída (m²):</strong> De " + str(st.session_state.get('area_min_form', 0.0)) + " a " + str(st.session_state.get('area_max_form', 5000.0)) + "</p>" if st.session_state.get('filtrar_area_dynamic_checkbox', False) else ""}

            <h2>Estatísticas dos Itens Selecionados</h2>
            <div class="highlight">
                <p><strong>Média do Valor de Transação (Selecionados):</strong> R$ {media_valor_selecionado_itbi:,.2f}</p>
                <p><strong>Média do Valor por m² (Selecionados):</strong> R$ {media_valor_m2_selecionado_itbi:,.2f}</p>
            </div>

            <h2>Dados Detalhados dos Itens Selecionados</h2>
            {tabela_html}
        </body>
        </html>
        """
            
        pdf_bytes = WeasyHTML(string=html_content).write_pdf()

        st.download_button(
            label=f"📥 Baixar PDF dos {len(selected_rows_for_action_itbi)} Itens Selecionados",
            data=pdf_bytes,
            file_name="relatorio_itbi_selecionados.pdf",
            mime="application/pdf",
            help="Clique para baixar o relatório em PDF com apenas os itens que você selecionou na tabela."
        )
    else:
        st.warning("Nenhum imóvel selecionado na tabela de ITBI. Selecione um ou mais imóveis para gerar um relatório específico.")
        if 'resultado_consulta_itbi' in st.session_state and not st.session_state.resultado_consulta_itbi.empty:
            media_valor_geral_itbi = st.session_state.resultado_consulta_itbi['Valor de Transação (declarado pelo contribuinte)'].mean()
            media_valor_m2_geral_itbi = st.session_state.resultado_consulta_itbi['Valor por m²'].mean()
            st.info(f"**Média de TODOS os resultados da consulta de ITBI:**")
            col_stats_geral1, col_stats_geral2 = st.columns(2)
            with col_stats_geral1:
                st.metric(label="Valor de Transação (Geral)", value=f"R$ {media_valor_geral_itbi:,.2f}")
            with col_stats_geral2:
                st.metric(label="Valor por m² (Geral)", value=f"R$ {media_valor_m2_geral_itbi:,.2f}")
        else:
            st.info("Nenhum dado de consulta de ITBI disponível para calcular médias.")

# --- NOVO: Seção de Comparação de Imóveis ---
st.header("⚖️ Comparação de Imóveis")

# Campos para o usuário digitar os detalhes do endereço do imóvel a ser comparado
col_comp_end1, col_comp_end2, col_comp_end3 = st.columns(3)
with col_comp_end1:
    logradouro_comparacao_input = st.text_input("Logradouro:", help="Nome da rua (ex: RUA EXEMPLO)", key="logradouro_comparacao_input").upper()
with col_comp_end2:
    numero_comparacao_input = st.number_input("Número:", min_value=0, value=0, step=1, help="Número do imóvel", key="numero_comparacao_input")
with col_comp_end3:
    complemento_comparacao_input = st.text_input("Complemento (opcional):", help="Ex: APTO 12, FUNDOS", key="complemento_comparacao_input").upper()


area_construida_buscada = None
if st.button("Buscar Área do Imóvel por Endereço"):
    if logradouro_comparacao_input and numero_comparacao_input > 0:
        area_construida_buscada = buscar_area_por_detalhes_endereco(
            logradouro_comparacao_input, 
            numero_comparacao_input, 
            complemento_comparacao_input
        )
        if area_construida_buscada is not None:
            st.success(f"Área Construída encontrada para '{logradouro_comparacao_input}, {numero_comparacao_input} {complemento_comparacao_input}': {area_construida_buscada:,.2f} m²")
            st.session_state['area_construida_buscada'] = area_construida_buscada
        else:
            st.warning(f"Nenhuma Área Construída encontrada para '{logradouro_comparacao_input}, {numero_comparacao_input} {complemento_comparacao_input}'. Tente refinar a busca.")
            st.session_state['area_construida_buscada'] = 0.0
    else:
        st.error("Por favor, digite o Logradouro e o Número para buscar a área.")
        st.session_state['area_construida_buscada'] = 0.0

# Recupera a área buscada da session_state (se existir)
area_construida_comparado_from_search = st.session_state.get('area_construida_buscada', 0.0)

st.markdown("---")
st.markdown("O valor por m² de referência será a **média dos imóveis de ITBI que você selecionou** na tabela acima.")

valor_m2_referencia = 0.0
imovel_referencia_info = ""

# Lógica para obter o valor de m² de referência (agora simplificada)
if 'df_para_exibir_formatado_itbi' in st.session_state and not selected_rows_for_action_itbi.empty:
    # Pega o valor original não formatado
    valor_m2_referencia = df_selecionado_original_itbi['Valor por m²'].mean()
    imovel_referencia_info = f"Média de **R$ {valor_m2_referencia:,.2f} / m²** dos imóveis de ITBI selecionados."
    st.success(imovel_referencia_info)
else:
    st.warning("Selecione um ou mais imóveis na tabela de ITBI acima para usar este método de comparação.")
    # Se nenhum imóvel de ITBI for selecionado, o valor de referência será 0.0
    # e o cálculo não prosseguirá até que um valor válido seja fornecido (pela seleção).
    valor_m2_referencia = 0.0
    imovel_referencia_info = "N/A (Nenhum imóvel de ITBI selecionado)"
    
st.markdown("---")

st.subheader("Dados do Imóvel a Ser Comparado")

# Campo de entrada para a área construída do imóvel a ser comparado
# Agora, o valor inicial VEM DA BUSCA e NÃO PODE SER ALTERADO MANUALMENTE
st.markdown(f"**Área Construída do Imóvel (m²):** `{area_construida_comparado_from_search:,.2f}` m²")
# Usamos o valor diretamente da session_state, sem um number_input editável aqui
area_construida_para_calculo = area_construida_comparado_from_search


if st.button("Calcular Valor Comparativo"):
    if valor_m2_referencia <= 0:
        st.error("Por favor, selecione um imóvel de ITBI para obter um Valor por m² de referência válido (> 0).")
    elif area_construida_para_calculo <= 0:
        st.error("Por favor, busque a Área Construída do imóvel a ser comparado pelo endereço.")
    else:
        # Calcular o valor comparativo (apenas com área construída)
        valor_comparativo_total = area_construida_para_calculo * valor_m2_referencia
        
        st.subheader("Estimativa de Valor Comparativo")
        st.markdown(f"**Valor por m² de Referência:** {imovel_referencia_info}")
        st.markdown(f"**Área Construída do Imóvel:** {area_construida_para_calculo:,.2f} m²")
        
        st.markdown("---")
        st.metric(label="**VALOR TOTAL ESTIMADO**", value=f"R$ {valor_comparativo_total:,.2f}", delta_color="off")


# --- Observações sobre os dados ---
if dados_itbi.empty and not submitted and 'df_para_exibir_formatado_itbi' not in st.session_state:
    st.info("Aguardando sua primeira consulta de ITBI. Verifique se os arquivos de dados estão configurados corretamente.")

# --- Explicação sobre a seleção de itens no PDF (atualizada) ---
st.sidebar.info(
    "**Nota sobre o PDF:**\n\n"
    "O relatório em PDF agora inclui **APENAS os imóveis que você selecionou** na tabela de ITBI. "
    "Use os checkboxes na tabela para escolher os itens que deseja incluir no relatório."
)
