# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variables
ENV COSMOS_PROTO_DECODE_BINARY=initia-decode
ENV COSMOS_PROTO_DECODE_LIMIT=10000
ENV COSMOS_PROTO_DECODE_BLOCK_LIMIT=10000
ENV TX_AMINO_LENGTH_CUTTOFF_LIMIT=0
ENV WALLET_PREFIX=initia1
ENV VALOPER_PREFIX=initiavaloper1
ENV TASK=download
ENV CHAINID=initiation-1

# Run app.py when the container launches
CMD ["python", "main.py"]
