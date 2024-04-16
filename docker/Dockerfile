FROM python:latest

RUN git clone https://github.com/vale46n1/immich_duplicate_finder.git && \
cd immich_duplicate_finder && \
pip install -r requirements.txt

CMD streamlit run app.py
