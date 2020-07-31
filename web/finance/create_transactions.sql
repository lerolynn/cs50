CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id integer NOT NULL, symbol varchar(30), shares integer, share_price float NOT NULL, datetime timestamp DEFAULT CURRENT_TIMESTAMP , FOREIGN KEY (user_id) REFERENCES users(id));