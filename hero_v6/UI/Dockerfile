FROM nginx:alpine

# Copia i file statici della UI nella directory di default di Nginx
COPY . /usr/share/nginx/html

# Espone la porta 80 standard per HTTP
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
