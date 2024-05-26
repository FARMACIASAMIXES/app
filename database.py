class Config:
    SECRET_KEY = 'quiensabequevayaaqui'

class MySql(Config):
    DEBUG = True
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'juarez'
    MYSQL_DB = 'farmacia'

config ={
    'credencialesDB': MySql
}