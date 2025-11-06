FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .
COPY . ./
EXPOSE 8000
CMD ["uvicorn", "bi10.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
