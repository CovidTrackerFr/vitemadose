FROM python

WORKDIR /usr/src/app
COPY . .

RUN pip install requests
RUN pip install pytz==2021.1
RUN pip install httpx==0.17.1
RUN pip install requests[socks]==2.25.1
RUN pip install pytest==6.2.2
RUN pip install beautifulsoup4==4.9.3

RUN ./scripts/install

CMD ["./scripts/scrape"]

