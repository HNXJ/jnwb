@echo off
echo Starting local Jupyter Server for Omission Project (V1-PFC Predictive Routing)
echo Compatible with local run and Google Colab integration...
echo.
echo Running command (using modern ServerApp syntax to avoid warnings):
echo jupyter notebook --ServerApp.allow_origin="https://colab.research.google.com" --ServerApp.port=8888 --ServerApp.port_retries=0 --no-browser
echo.

jupyter notebook --ServerApp.allow_origin="https://colab.research.google.com" --ServerApp.port=8888 --ServerApp.port_retries=0 --no-browser
pause
