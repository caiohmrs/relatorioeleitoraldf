import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
from fpdf import FPDF
import tempfile

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Relatórios Eleitorais", layout="wide")

# --- CARREGAMENTO DE DADOS ---
@st.cache_data
def carregar_dados():
    arquivos = {

        'Governador': 'localvotacao_governador.csv'
        
    }
    
    dados = {}
    erros = []

    colunas_padrao = ['nm_votavel', 'nr_zona', 'nm_local_votacao', 'qt_votos']
    rename_map = {'nm_votavel':'Nome', 'nr_zona': 'Zona', 'nm_local_votacao': 'Local de Votação', 'qt_votos': 'Votos'}

    for cargo, arquivo in arquivos.items():
        if os.path.exists(arquivo):
            try:
                df = pd.read_csv(arquivo, sep=';')
                # Verifica se as colunas existem
                if all(col in df.columns for col in colunas_padrao):
                    df = df[colunas_padrao]
                    df = df.rename(columns=rename_map)
                    dados[cargo] = df
                else:
                    erros.append(f"Arquivo {arquivo} não tem as colunas corretas.")
            except Exception as e:
                erros.append(f"Erro ao ler {arquivo}: {e}")
        else:
            erros.append(f"Arquivo {arquivo} não encontrado na pasta.")
    
    return dados, erros

# --- FUNÇÃO DE GERAÇÃO DO PDF (CORRIGIDA) ---
def gerar_pdf_bytes(df, nome_candidato):
    # 1. MAPEAMENTO DE TERRITÓRIOS (DF)
    regioes = {
        1: "Asa Sul", 2: "Paranoá, Varjão, Itapoã, Lago Norte", 3: "Taguatinga",
        4: "Santa Maria", 5: "Sobradinho", 6: "Planaltina", 8: "Ceilândia Centro",
        9: "Guará", 10: "N. Bandeirante, R. Fundo, Park Way", 11: "Cruzeiro, Sudoeste",
        13: "Samambaia", 14: "Asa Norte", 15: "Águas Claras", 16: "Ceilândia Norte, Brazlândia",
        17: "Gama", 18: "Lago Sul, J. Botânico, S. Sebastião", 19: "Taguatinga Norte",
        20: "Ceilândia Sul", 21: "Recanto das Emas"
    }

    # 2. CÁLCULOS
    resumo_geral = df.groupby(['Zona', 'Nome'])['Votos'].sum().reset_index()
    resumo_geral['Rank'] = resumo_geral.groupby('Zona')['Votos'].rank(ascending=False, method='min').astype(int)
    
    media_zona = resumo_geral.groupby('Zona')['Votos'].mean().reset_index().rename(columns={'Votos': 'Media_Votos'})
    resumo_geral = resumo_geral.merge(media_zona, on='Zona')
    
    stats_candidato = resumo_geral[resumo_geral['Nome'] == nome_candidato].sort_values('Zona')
    
    if stats_candidato.empty:
        return None, "Candidato sem votos registrados."

    total_geral_cand = stats_candidato['Votos'].sum()

    # --- GRÁFICO DE PERFORMANCE ---
    fig, ax = plt.subplots(figsize=(10, 5))
    x_labels = [f"Z{z}" for z in stats_candidato['Zona']]
    ax.bar(x_labels, stats_candidato['Votos'], label='Seus Votos', color='royalblue')
    ax.plot(x_labels, stats_candidato['Media_Votos'], label='Média da Zona', color='orange', marker='o')
    ax.set_title('Performance por Zona Eleitoral')
    ax.legend()
    
    # CORREÇÃO AQUI: Criar, fechar o handle, e só usar o nome
    temp_chart = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    temp_chart.close() # <--- IMPORTANTE: Fecha o arquivo para o Windows liberar
    
    fig.savefig(temp_chart.name)
    plt.close(fig)

    # --- CLASSE DO PDF ---
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, f'Relatório Territorial: {nome_candidato}', ln=True, align='C')
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            texto = f"© Caio Henrique Machado | WhatsApp: (61) 99878-8292 | Página {self.page_no()}"
            self.cell(0, 10, texto, align='C')

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # 3. PÁGINAS POR ZONA
    for zona in sorted(stats_candidato['Zona'].unique()):
        pdf.add_page()
        nome_regiao = regioes.get(zona, "Região não mapeada")
        v_zona = stats_candidato[stats_candidato['Zona'] == zona]['Votos'].values[0]
        r_zona = stats_candidato[stats_candidato['Zona'] == zona]['Rank'].values[0]
        
        pdf.set_font("Arial", 'B', 11)
        pdf.set_fill_color(230, 230, 230)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, f"ZONA {zona} - {nome_regiao.upper()}", ln=True, fill=True, align='C')
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, f"Votos: {v_zona} | Ranking: {r_zona}º lugar", ln=True, align='C')
        
        pdf.ln(2)
        escolas = df[(df['Nome'] == nome_candidato) & (df['Zona'] == zona)].sort_values(by='Votos', ascending=False)
        
        pdf.set_font("Arial", 'B', 9)
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(150, 7, "Unidade Escolar / Local", border=1, fill=True)
        pdf.cell(40, 7, "Votos", border=1, ln=True, align='C', fill=True)
        
        pdf.set_font("Arial", size=8)
        for _, row in escolas.iterrows():
            pdf.cell(150, 6, str(row['Local de Votação'])[:75], border=1)
            pdf.cell(40, 6, str(row['Votos']), border=1, ln=True, align='C')

    # 4. RANKING FINAL
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 15, "RESUMO COMPETITIVO POR TERRITÓRIO", ln=True, align='C')
    
    for zona in sorted(stats_candidato['Zona'].unique()):
        nome_regiao = regioes.get(zona, "Outros")
        pdf.set_font("Arial", 'B', 10)
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(0, 8, f"ZONA {zona} ({nome_regiao})", ln=True, fill=True)
        
        zona_full = resumo_geral[resumo_geral['Zona'] == zona].sort_values('Rank')
        top_5 = zona_full.head(5)
        candidato_no_top5 = not top_5[top_5['Nome'] == nome_candidato].empty
        
        pdf.set_font("Arial", size=9)
        for _, comp in top_5.iterrows():
            fill = (255, 255, 180) if comp['Nome'] == nome_candidato else (255, 255, 255)
            pdf.set_fill_color(*fill)
            pdf.cell(15, 6, f"{comp['Rank']}º", border=1, align='C', fill=True)
            pdf.cell(135, 6, f" {comp['Nome']}", border=1, fill=True)
            pdf.cell(40, 6, str(comp['Votos']), border=1, ln=True, align='C', fill=True)
        
        if not candidato_no_top5:
            c_info = stats_candidato[stats_candidato['Zona'] == zona].iloc[0]
            pdf.set_fill_color(255, 210, 210)
            pdf.cell(15, 6, f"{c_info['Rank']}º", border=1, align='C', fill=True)
            pdf.cell(135, 6, f" [POSIÇÃO ATUAL] {nome_candidato}", border=1, fill=True)
            pdf.cell(40, 6, str(c_info['Votos']), border=1, ln=True, align='C', fill=True)
        pdf.ln(4)

    # 5. GRÁFICO FINAL
    pdf.add_page()
    pdf.image(temp_chart.name, x=10, y=20, w=190)
    pdf.set_y(160)
    pdf.set_font("Arial", 'B', 22)
    pdf.set_fill_color(40, 70, 120); pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 25, f"VOTAÇÃO TOTAL DF: {total_geral_cand} VOTOS", ln=True, align='C', fill=True)

    # Gera o arquivo final
    # CORREÇÃO TAMBÉM NO PDF: Criar, fechar, depois usar
    pdf_output = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_output.close() # <--- Fecha o handle do PDF também
    
    pdf.output(pdf_output.name)
    
    # Limpeza segura
    try:
        os.remove(temp_chart.name)
    except Exception as e:
        print(f"Aviso: não foi possível deletar a imagem temporária: {e}")
    
    return pdf_output.name, None

# --- INTERFACE PRINCIPAL ---

st.title("🗳️ Gerador de Relatórios Eleitorais - DF")
st.markdown("Selecione o tipo de eleição e o candidato para gerar o PDF com análise territorial. #Este app é uma previa de um script para gerar relatorios profundos sobre cada candidato do DF nas eleições de 2022, separando por local de votação e trazendo insights previos sobre cada candidato frente a eleição que concorreu. Na prévia, apenas o relatório para governadores está disponivel, porém caso deseje uso total do aplicativo entrar em contato comigo pelo whatsapp. Posso gerar este mesmo app gerador de relatório para qualquer Estado e qualquer eleição desejada. #Whatsapp: Caio Henrique wa.me/5561998788292")

# Carrega Dados
dados_dict, erros_log = carregar_dados()

if erros_log:
    st.error("Erros encontrados no carregamento de arquivos:")
    for erro in erros_log:
        st.warning(erro)
    st.info("Certifique-se de que os arquivos .csv estão na mesma pasta que este script.")

if dados_dict:
    # Sidebar
    st.sidebar.header("Configurações")
    tipo_eleicao = st.sidebar.selectbox("Selecione o Cargo", list(dados_dict.keys()))
    
    df_selecionado = dados_dict[tipo_eleicao]
    
    # Dropdown de Candidatos
    lista_candidatos = sorted(df_selecionado['Nome'].unique())
    candidato_selecionado = st.sidebar.selectbox("Selecione o Candidato", lista_candidatos)
    
    st.write(f"### Analisando: {candidato_selecionado} ({tipo_eleicao})")
    
    # Botão de Ação
    if st.button("Gerar Relatório e Pré-visualizar"):
        with st.spinner('Processando dados e gerando PDF...'):
            
            # Gera PDF
            caminho_pdf, erro_pdf = gerar_pdf_bytes(df_selecionado, candidato_selecionado)
            
            if erro_pdf:
                st.error(erro_pdf)
            else:
                # Mostra estatística rápida na tela
                total_votos = df_selecionado[df_selecionado['Nome'] == candidato_selecionado]['Votos'].sum()
                st.metric(label="Total de Votos", value=total_votos)
                
                # Mostra o gráfico na tela também (Recriando lógica simples do gráfico)
                resumo = df_selecionado.groupby(['Zona', 'Nome'])['Votos'].sum().reset_index()
                cand_stats = resumo[resumo['Nome'] == candidato_selecionado]
                
                st.subheader("Prévia da Performance por Zona")
                st.bar_chart(cand_stats.set_index('Zona')['Votos'])
                
                # Botão de Download
                with open(caminho_pdf, "rb") as pdf_file:
                    PDFbyte = pdf_file.read()

                st.download_button(
                    label="📥 Baixar Relatório PDF Completo",
                    data=PDFbyte,
                    file_name=f"Relatorio_{candidato_selecionado.replace(' ', '_')}.pdf",
                    mime='application/pdf'
                )
                
                st.success("Relatório gerado com sucesso! Clique no botão acima para baixar.")
