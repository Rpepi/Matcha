from faker import Faker
import random

profiles= []
fake = Faker('fr_FR')
for _ in range(500):
    user = {
        "username": fake.user_name(),
        "email": fake.email(),
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "bio": fake.text(max_nb_chars=200),
        "gender": random.choice(["male", "female", "other"]),
        "orientation": random.choice(["hetero", "homo", "bi"]),
        "latitude": fake.latitude(),
        "longitude": fake.longitude(),
        "birth_date": fake.date_of_birth(minimum_age=18, maximum_age=60),
    }