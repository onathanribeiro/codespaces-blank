# processar_imoveis_sp.py
import pandas as pd
import sqlite3
import os

# --- ATENÇÃO: CONFIGURAÇÃO OBRIGATÓRIA ---
CAMINHO_PLANILHA_GRANDE = 'IPTU_2025.csv'

COLUNAS_ORIGINAIS_INTERESSE = [
    'NUMERO DO CONTRIBUINTE',
    'NOME DE LOGRADOURO DO IMOVEL',
    'NUMERO DO IMOVEL',
    'COMPLEMENTO DO IMOVEL',
    'AREA CONSTRUIDA'
]

COLUNAS_DB_MAP = {
    'NUMERO DO CONTRIBUINTE': 'contribuinte_num',
    'NOME DE LOGRADOURO DO IMOVEL': 'logradouro_nome',
    'NUMERO DO IMOVEL': 'numero_imovel',
    'COMPLEMENTO DO IMOVEL': 'complemento_imovel',
    'AREA CONSTRUIDA': 'area_construida'
}

# --- FIM DA CONFIGURAÇÃO OBRIGATÓRIA ---


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_DB_SAIDA = os.path.join(BASE_DIR, 'data', 'imoveis_sp_reduzido.db') 

def processar_e_salvar_para_sqlite(input_csv_path, output_db_path, original_cols, db_col_map):
    print(f"Iniciando processamento de {input_csv_path}...")
    
    os.makedirs(os.path.dirname(output_db_path), exist_ok=True)
    conn = sqlite3.connect(output_db_path)
    
    try:
        # Conectar ao banco de dados SQLite
        # Garante que o diretório de saída exista

        # ESTE É O BLOCO CORRIGIDO. ATENÇÃO AOS ESPAÇOS:
        try: # 4 espaços de indentação
            df_chunks = pd.read_csv(input_csv_path, encoding='utf-8', sep=';', chunksize=100000) # 8 espaços de indentação
        except UnicodeDecodeError: # 4 espaços de indentação (alinhado com o 'try' externo)
            print("Encoding UTF-8 falhou. Tentando latin-1...") # 8 espaços de indentação
            df_chunks = pd.read_csv(input_csv_path, encoding='latin-1', sep=';', chunksize=100000) # 8 espaços de indentação
        # FIM DO BLOCO CORRIGIDO

        for i, chunk in enumerate(df_chunks):
            print(f"Processando chunk {i+1} de {len(chunk)} linhas...")
            
            df_reduzido = chunk[original_cols].rename(columns=db_col_map).copy()
            
            df_reduzido['contribuinte_num'] = df_reduzido['contribuinte_num'].astype(str).str.strip()
            df_reduzido['logradouro_nome'] = df_reduzido['logradouro_nome'].astype(str).str.upper().str.strip()
            df_reduzido['numero_imovel'] = pd.to_numeric(df_reduzido['numero_imovel'], errors='coerce').fillna(0).astype(int)
            df_reduzido['complemento_imovel'] = df_reduzido['complemento_imovel'].astype(str).str.upper().str.strip().replace('NAN', '')
            df_reduzido['area_construida'] = pd.to_numeric(df_reduzido['area_construida'], errors='coerce').fillna(0)

            df_reduzido['endereco_completo_formatado'] = df_reduzido.apply(
                lambda row: f"{row['logradouro_nome']}, {row['numero_imovel']}{' ' + row['complemento_imovel'] if row['complemento_imovel'] else ''}".strip(),
                axis=1
            )
            df_reduzido['endereco_completo_formatado'] = df_reduzido['endereco_completo_formatado'].str.upper()

            if i == 0:
                df_reduzido.to_sql('imoveis_sp', conn, if_exists='replace', index=False)
            else:
                df_reduzido.to_sql('imoveis_sp', conn, if_exists='append', index=False)
        
        print(f"Processamento concluído. Dados salvos em {output_db_path}")

    except Exception as e:
        print(f"Erro durante o processamento: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    if os.path.exists(CAMINHO_PLANILHA_GRANDE):
        processar_e_salvar_para_sqlite(
            CAMINHO_PLANILHA_GRANDE, 
            CAMINHO_DB_SAIDA, 
            COLUNAS_ORIGINAIS_INTERESSE, 
            COLUNAS_DB_MAP
        )
    else:
        print(f"Erro: Planilha de 1GB não encontrada em {CAMINHO_PLANILHA_GRANDE}.")
        print("Por favor, verifique o caminho e certifique-se de que a planilha está lá.")