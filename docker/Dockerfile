FROM python:latest

RUN git clone https://github.com/vale46n1/immich_duplicate_finder.git && \
cd immich_duplicate_finder && \
pip install -r requirements.txt

WORKDIR /immich_duplicate_finder
EXPOSE 8501
HEALTHCHECK CMD curl -fsS http://127.0.0.1:8501 | grep -c 'title>Streamlit</title' || exit 1

CMD streamlit run app.py
