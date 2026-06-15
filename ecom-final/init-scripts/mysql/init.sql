-- MySQL init script: tạo database cho payment-service
CREATE DATABASE IF NOT EXISTS paymentdb;
GRANT ALL PRIVILEGES ON paymentdb.* TO 'root'@'%';
FLUSH PRIVILEGES;
