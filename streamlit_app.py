import streamlit as st
import pandas as pd
import os
import io
import datetime
from weasyprint import HTML as WeasyHTML

# --- Configurações Iniciais do Streamlit ---
st.set_page_config(layout="wide", page_title="Consulta de ITBI")

st.title("🏡 Consulta de Guias de ITBI")
st.markdown("Use os filtros abaixo para encontrar transações de imóveis e gerar relatórios.")

# --- Caminhos dos Arquivos (AJUSTADO PARA CAMINHOS RELATIVOS) ---
# O script streamlit_app.py está na raiz do repositório.
# A pasta 'data' está no mesmo nível.
# Então, o caminho relativo é 'data/'.

# Define o diretório base como o diretório onde o script está sendo executado
BASE_DIR = os.path.dirname(__file__) 

caminho_pkl = os.path.join(BASE_DIR, 'data', 'dados_itbi_unificados.pkl')
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
    'Data de Transação', 'Área Construída (m2)'
]
abas_para_ignorar = ['LEGENDA', 'EXPLICAÇÕES', 'Tabela de USOS', 'Tabela de PADRÕES']

colunas_desejadas_excel = [
    'Nome do Logradouro', 'Número', 'Complemento',
    'Valor de Transação (declarado pelo contribuinte)',
    'Data de Transação', 'Área Construída (m2)'
]
abas_para_ignorar = ['LEGENDA', 'EXPLICAÇÕES', 'Tabela de USOS', 'Tabela de PADRÕES']

# --- Função para Carregar Planilhas ---
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

@st.cache_data
def carregar_e_processar_dados():
    """Carrega dados de PKL ou Excel e os pré-processa."""
    dados_carregados = pd.DataFrame()
    
    if os.path.exists(caminho_pkl):
        try:
            dados_carregados = pd.read_pickle(caminho_pkl)
            st.success("Dados carregados a partir do arquivo .pkl!")
        except Exception as e:
            st.warning(f"Erro ao carregar .pkl: {e}. Tentando carregar do Excel.")
    
    if dados_carregados.empty:
        st.info("Arquivo .pkl não encontrado ou com erro. Carregando as planilhas do Excel...")
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
                dados_carregados['Nome do Logradouro'] = dados_carregados['Nome do Logradouro'].astype(str).str.upper()
                try:
                    os.makedirs(os.path.dirname(caminho_pkl), exist_ok=True)
                    dados_carregados.to_pickle(caminho_pkl)
                    st.success("Dados carregados do Excel e salvos no formato .pkl!")
                except Exception as e:
                    st.warning(f"Não foi possível salvar o .pkl em {caminho_pkl}: {e}. O app continuará com os dados em memória.")
            else:
                st.error("Nenhum arquivo Excel válido encontrado ou carregado. O DataFrame de dados está vazio.")
        else:
            st.error("Não foi possível carregar dados de PKL ou Excel. Verifique os caminhos e permissões.")
    
    if not dados_carregados.empty:
        dados_processados = dados_carregados.copy()
        
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

dados = carregar_e_processar_dados()

# Definir as colunas base para exibir
colunas_base_exibicao = [
    'Nome do Logradouro', 'Número', 'Complemento',
    'Valor de Transação (declarado pelo contribuinte)',
    'Data de Transação', 'Área Construída (m2)', 'Valor por m²'
]

# --- Interface de Busca (Streamlit) ---
st.header("🔍 Critérios de Busca")

# Checkboxes fora do formulário para comportamento dinâmico
col_dynamic_checkbox1, col_dynamic_checkbox2 = st.columns(2)
with col_dynamic_checkbox1:
    busca_range = st.checkbox("Buscar por range de número?", key="busca_range_dynamic_checkbox")
with col_dynamic_checkbox2:
    filtrar_area = st.checkbox("Filtrar por Área Construída (m²)?", key="filtrar_area_dynamic_checkbox")

# Formulário para os inputs de busca
with st.form("busca_form"):
    nome_rua = st.text_input("Nome da Rua:", help="Parte ou nome completo da rua.", key="nome_rua_input").upper()

    # Campos de input para número (condicionais, baseados nos checkboxes dinâmicos)
    col_num1, col_num2 = st.columns(2)
    with col_num1:
        if busca_range:
            num_min = st.number_input("Número Mínimo:", min_value=0, value=st.session_state.get('num_min_input', 0), step=1, key="num_min_form")
        else:
            num_exato = st.number_input("Número Exato:", min_value=0, value=st.session_state.get('num_exato_input', 0), step=1, key="num_exato_form")
    with col_num2:
        if busca_range:
            num_max = st.number_input("Número Máximo:", min_value=0, value=st.session_state.get('num_max', 10000), step=1, key="num_max_form")
    
    # Campos de input para área (condicionais, baseados nos checkboxes dinâmicos)
    if filtrar_area:
        col_area1, col_area2 = st.columns(2)
        with col_area1:
            area_min = st.number_input("Área Mínima (m²):", min_value=0, value=st.session_state.get('area_min', 0), step=1, key="area_min_form")
        with col_area2:
            area_max = st.number_input("Área Máxima (m²):", min_value=0, value=st.session_state.get('area_max', 5000), step=1, key="area_max_form")
    
    submitted = st.form_submit_button("Consultar")

# --- Lógica de Consulta e Exibição de Resultados ---
if submitted:
    if dados.empty:
        st.error("Não há dados carregados para realizar a consulta. Verifique os caminhos dos arquivos e o carregamento inicial.")
        st.session_state.resultado_consulta = pd.DataFrame()
        st.session_state.df_para_exibir_formatado = pd.DataFrame()
    else:
        st.subheader("📊 Resultados da Consulta")
        
        df_filtrado = dados.copy()
        
        # Acessa o nome da rua do session_state, pois ele está no form
        nome_rua_valor = st.session_state.get('nome_rua_input', '')
        if nome_rua_valor:
            df_filtrado = df_filtrado[df_filtrado['Nome do Logradouro'].str.contains(nome_rua_valor, case=False, na=False)]

        # Lógica de filtro para número: AGORA USA O VALOR DO CHECKBOX 'busca_range_dynamic_checkbox'
        # e as chaves dos inputs dentro do formulário ('num_min_form', 'num_exato_form', etc.)
        if st.session_state.get('busca_range_dynamic_checkbox', False):
            min_val = st.session_state.get('num_min_form', 0)
            max_val = st.session_state.get('num_max_form', 10000)
            df_filtrado = df_filtrado[(df_filtrado['Número'] >= min_val) & (df_filtrado['Número'] <= max_val)]
        else:
            exact_val = st.session_state.get('num_exato_form', 0)
            df_filtrado = df_filtrado[df_filtrado['Número'] == exact_val]

        # Lógica de filtro para área: AGORA USA O VALOR DO CHECKBOX 'filtrar_area_dynamic_checkbox'
        # e as chaves dos inputs dentro do formulário ('area_min_form', 'area_max_form', etc.)
        if st.session_state.get('filtrar_area_dynamic_checkbox', False):
            min_area = st.session_state.get('area_min_form', 0)
            max_area = st.session_state.get('area_max_form', 5000)
            df_filtrado = df_filtrado[(df_filtrado['Área Construída (m2)'] >= min_area) & (df_filtrado['Área Construída (m2)'] <= max_area)]

        if df_filtrado.empty:
            st.warning("Nenhum resultado encontrado com os critérios de busca especificados.")
            st.session_state.resultado_consulta = pd.DataFrame()
            st.session_state.df_para_exibir_formatado = pd.DataFrame()
        else:
            st.session_state.resultado_consulta = df_filtrado.reset_index(drop=True)

            colunas_para_exibir_final = colunas_base_exibicao[:]
            if 'Complemento' in st.session_state.resultado_consulta.columns and st.session_state.resultado_consulta['Complemento'].isnull().all():
                colunas_para_exibir_final.remove('Complemento')

            df_para_exibir_raw = st.session_state.resultado_consulta[[col for col in colunas_para_exibir_final if col in st.session_state.resultado_consulta.columns]].copy()
            
            df_para_exibir_formatado = df_para_exibir_raw.copy()
            df_para_exibir_formatado['Valor de Transação (declarado pelo contribuinte)'] = df_para_exibir_formatado['Valor de Transação (declarado pelo contribuinte)'].map('R$ {:,.2f}'.format)
            df_para_exibir_formatado['Valor por m²'] = df_para_exibir_formatado['Valor por m²'].map('R$ {:,.2f}'.format)
            
            # Adicionar a coluna 'Selecionar' e REORDENAR
            df_para_exibir_formatado['Selecionar'] = False
            cols_ordered = ['Selecionar'] + [col for col in df_para_exibir_formatado.columns if col != 'Selecionar']
            df_para_exibir_formatado = df_para_exibir_formatado[cols_ordered]

            st.session_state.df_para_exibir_formatado = df_para_exibir_formatado

# --- Exibição da Tabela (Fora do bloco 'if submitted' para que persista) ---
if 'df_para_exibir_formatado' in st.session_state and not st.session_state.df_para_exibir_formatado.empty:
    st.subheader("Resultados Detalhados (Selecione para o PDF)")

    edited_df = st.data_editor(
        st.session_state.df_para_exibir_formatado,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(
                "Gerar PDF",
                help="Selecione as linhas para gerar PDFs individuais",
                default=False,
            )
        },
        key="data_editor_results"
    )
    
    selected_rows_for_pdf = edited_df[edited_df["Selecionar"]]

    st.subheader("Sumário e Ações")

    if not selected_rows_for_pdf.empty:
        selected_indices_original = selected_rows_for_pdf.index
        df_selecionado_original = st.session_state.resultado_consulta.loc[selected_indices_original]

        media_valor_selecionado = df_selecionado_original['Valor de Transação (declarado pelo contribuinte)'].mean()
        media_valor_m2_selecionado = df_selecionado_original['Valor por m²'].mean()

        st.info(f"**Média dos Itens SELECIONADOS ({len(selected_rows_for_pdf)} imóveis):**")
        col_stats_sel1, col_stats_sel2 = st.columns(2)
        with col_stats_sel1:
            st.metric(label="Valor de Transação (Selecionados)", value=f"R$ {media_valor_selecionado:,.2f}")
        with col_stats_sel2:
            st.metric(label="Valor por m² (Selecionados)", value=f"R$ {media_valor_m2_selecionado:,.2f}")

        st.markdown("---") 

        df_para_pdf_final = selected_rows_for_pdf.copy()
        
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
                body {{ font-family: Arial, sans-serif; margin: 20px; font-size: 10pt; }} /* Reduzido o tamanho da fonte */
                h1 {{ color: #333; font-size: 18pt; }}
                h2 {{ color: #555; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 20px; font-size: 14pt; }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                    table-layout: fixed; /* Força o layout da tabela a ser fixo */
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 6px; /* Reduzido o padding */
                    text-align: left;
                    word-wrap: break-word; /* Permite quebra de palavras longas */
                    overflow-wrap: break-word; /* Para compatibilidade com browsers */
                    font-size: 9pt; /* Reduzido o tamanho da fonte para células */
                }}
                th {{ background-color: #f2f2f2; }}
                .highlight {{ background-color: #e0f2f7; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
                .section-header {{ font-weight: bold; margin-top: 15px; }}
                p {{ font-size: 10pt; }} /* Reduzido o tamanho da fonte para parágrafos */
            </style>
        </head>
        <body>
            <h1>Relatório de Consulta de ITBI</h1>
            <p><strong>Data da Geração:</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>

            <h2>Parâmetros da Consulta</h2>
            <p><strong>Nome da Rua Pesquisada:</strong> {st.session_state.get('nome_rua_input', 'N/A').upper()}</p>
            <p><strong>Número da Busca:</strong> {"De " + str(st.session_state.get('num_min_form', 0)) + " a " + str(st.session_state.get('num_max_form', 10000)) if st.session_state.get('busca_range_dynamic_checkbox', False) else "Exato: " + str(st.session_state.get('num_exato_form', 0))}</p>
            {"<p><strong>Área Construída (m²):</strong> De " + str(st.session_state.get('area_min_form', 0)) + " a " + str(st.session_state.get('area_max_form', 5000)) + "</p>" if st.session_state.get('filtrar_area_dynamic_checkbox', False) else ""}

            <h2>Estatísticas dos Itens Selecionados</h2>
            <div class="highlight">
                <p><strong>Média do Valor de Transação (Selecionados):</strong> R$ {media_valor_selecionado:,.2f}</p>
                <p><strong>Média do Valor por m² (Selecionados):</strong> R$ {media_valor_m2_selecionado:,.2f}</p>
            </div>

            <h2>Dados Detalhados dos Itens Selecionados</h2>
            {tabela_html}
        </body>
        </html>
        """
            
        pdf_bytes = WeasyHTML(string=html_content).write_pdf()

        st.download_button(
            label=f"📥 Baixar PDF dos {len(selected_rows_for_pdf)} Itens Selecionados",
            data=pdf_bytes,
            file_name="relatorio_itbi_selecionados.pdf",
            mime="application/pdf",
            help="Clique para baixar o relatório em PDF com apenas os itens que você selecionou na tabela."
        )
    else:
        st.warning("Nenhum imóvel selecionado na tabela. Selecione um ou mais imóveis para gerar um relatório específico.")
        if 'resultado_consulta' in st.session_state and not st.session_state.resultado_consulta.empty:
            media_valor_geral = st.session_state.resultado_consulta['Valor de Transação (declarado pelo contribuinte)'].mean()
            media_valor_m2_geral = st.session_state.resultado_consulta['Valor por m²'].mean()
            st.info(f"**Média de TODOS os resultados da consulta:**")
            col_stats_geral1, col_stats_geral2 = st.columns(2)
            with col_stats_geral1:
                st.metric(label="Valor de Transação (Geral)", value=f"R$ {media_valor_geral:,.2f}")
            with col_stats_geral2:
                st.metric(label="Valor por m² (Geral)", value=f"R$ {media_valor_m2_geral:,.2f}")
        else:
            st.info("Nenhum dado de consulta disponível para calcular médias.")

# --- Observações sobre os dados ---
if dados.empty and not submitted and 'df_para_exibir_formatado' not in st.session_state:
    st.info("Aguardando sua primeira consulta. Verifique se os arquivos de dados estão configurados corretamente.")

# --- Explicação sobre a seleção de itens no PDF (atualizada) ---
st.sidebar.info(
    "**Nota sobre o PDF:**\n\n"
    "O relatório em PDF agora inclui **APENAS os imóveis que você selecionou** na tabela acima. "
    "Use os checkboxes na tabela para escolher os itens que deseja incluir no relatório."
)