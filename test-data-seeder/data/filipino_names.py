"""Common Filipino first names and surnames for realistic test workers."""
import random

FIRST_NAMES_MALE = [
    "Juan", "Jose", "Mario", "Andres", "Ramon", "Roberto", "Ricardo", "Renato",
    "Rey", "Roel", "Reynaldo", "Romeo", "Rolando", "Ronaldo", "Robert", "Junior",
    "Joel", "Joseph", "Jerome", "Jericho", "Eric", "Edwin", "Eddie", "Eduardo",
    "Carlo", "Carlos", "Cristobal", "Dante", "Daniel", "Dennis", "David", "Glenn",
    "Bryan", "Brian", "Mark", "Marvin", "Marlon", "Miguel", "Manuel", "Michael",
    "Marcelino", "Macario", "Felipe", "Florencio", "Fernando", "Francisco",
    "Gerardo", "Gilbert", "Gabriel", "Hector", "Henry", "Ignacio", "Isidro",
    "Julio", "Kenneth", "Lloyd", "Leandro", "Leonardo", "Lito", "Noel", "Norman",
    "Oliver", "Oscar", "Pablo", "Patrick", "Paulo", "Percival", "Peter", "Philip",
    "Rafael", "Ramil", "Raul", "Rico", "Rodel", "Rodrigo", "Rogelio", "Ronald",
    "Ronnie", "Roy", "Ruben", "Salvador", "Santiago", "Sergio", "Teodoro",
    "Teofilo", "Tomas", "Tony", "Ulysses", "Valentino", "Vicente", "Victor",
    "Virgilio", "Wilfredo", "Wilson", "Xavier", "Joey", "Jojo", "Bong", "Boy",
    "Jun", "Reggie", "Christian", "Anthony",
]

FIRST_NAMES_FEMALE = [
    "Maria", "Elena", "Cristina", "Catalina", "Carmen", "Conchita", "Corazon",
    "Cynthia", "Dalisay", "Diana", "Divina", "Dolores", "Edna", "Elisa",
    "Elizabeth", "Emilia", "Emma", "Erlinda", "Esperanza", "Estrella", "Eva",
    "Evangeline", "Felicidad", "Filomena", "Florinda", "Francisca", "Gloria",
    "Grace", "Helen", "Imelda", "Jenny", "Jessa", "Jocelyn", "Josefina",
    "Josephine", "Juana", "Julia", "Karen", "Leticia", "Liezel", "Linda",
    "Lorna", "Lourdes", "Lucia", "Luz", "Lydia", "Margarita", "Maricel",
    "Marisol", "Marites", "Marlene", "Mary", "Melinda", "Mercedes", "Michelle",
    "Milagros", "Monica", "Myrna", "Natividad", "Nelia", "Nenita", "Nerissa",
    "Nida", "Norma", "Olivia", "Patricia", "Paula", "Pilar", "Priscilla",
    "Rebecca", "Regina", "Remedios", "Rita", "Rosalia", "Rosalinda", "Rosario",
    "Rose", "Rowena", "Ruth", "Sandra", "Sarah", "Soledad", "Sonia", "Susana",
    "Sylvia", "Teresa", "Teresita", "Trinidad", "Veronica", "Victoria",
    "Violeta", "Virginia", "Vivian", "Yolanda", "Zenaida", "Andrea", "Angela",
    "Christine",
]

SURNAMES = [
    "Cruz", "Reyes", "Santos", "Garcia", "Mendoza", "Castro", "Torres", "Ramos",
    "Flores", "Bautista", "Villanueva", "Aquino", "Lim", "Tan", "Chua", "Sy",
    "Ong", "Yu", "dela Cruz", "San Jose", "Santiago", "Domingo", "Aguilar",
    "Aguinaldo", "Alcantara", "Alvarado", "Bacani", "Banaag", "Banzon",
    "Belarmino", "Beltran", "Bonifacio", "Buenaventura", "Cabrera", "Calderon",
    "Camacho", "Capulong", "Cariño", "Castillo", "Cervantes", "Chavez",
    "Concepcion", "Corpuz", "Cortes", "Crisostomo", "Cuevas", "Custodio",
    "dela Pena", "dela Rosa", "del Rosario", "Diaz", "Dimaculangan", "Dizon",
    "Enriquez", "Escobar", "Espino", "Estrada", "Eugenio", "Evangelista",
    "Fajardo", "Fernandez", "Ferrer", "Francisco", "Galang", "Galvez",
    "Geronimo", "Gomez", "Gonzales", "Gonzalez", "Guevara", "Gutierrez",
    "Hernandez", "Herrera", "Ignacio", "Imperial", "Jacinto", "Javier",
    "Jimenez", "Jocson", "Lacson", "Lagman", "Lim", "Liwanag", "Lopez",
    "Macaranas", "Madrigal", "Magbanua", "Malabanan", "Manuel", "Marasigan",
    "Marquez", "Martinez", "Mendoza", "Molina", "Morales", "Munoz", "Narciso",
    "Navarro", "Nazario", "Nepomuceno", "Nicolas", "Ocampo", "Ortega",
    "Pagaduan", "Palaganas", "Panganiban", "Pangilinan", "Pascual", "Pelayo",
    "Perez", "Pineda", "Pulido", "Puno", "Quintos", "Quirino", "Ramos",
    "Reyes", "Rivera", "Robles", "Romero", "Roxas", "Ruiz", "Salonga",
    "Salvador", "Samson", "Sanchez", "Sandoval", "Santiago", "Santos",
    "Sarmiento", "Serrano", "Silva", "Sison", "Soriano", "Sotto", "Suarez",
    "Tagle", "Tan", "Tanchanco", "Tantoco", "Tayag", "Tenorio", "Tiu",
    "Tolentino", "Torres", "Trinidad", "Tuazon", "Uy", "Valdez", "Valenzuela",
    "Vargas", "Vasquez", "Velasco", "Velasquez", "Vergara", "Villa",
    "Villanueva", "Villar", "Yap", "Zamora",
]


def random_full_name(rng: random.Random | None = None) -> str:
    r = rng or random
    pool = FIRST_NAMES_MALE + FIRST_NAMES_FEMALE
    first = r.choice(pool)
    last = r.choice(SURNAMES)
    return f"{first} {last}"


def random_worker_name(rng: random.Random | None = None) -> str:
    """Returns a unique-ish worker_name (first.last or first_last lowercase)."""
    r = rng or random
    full = random_full_name(r)
    parts = full.lower().replace("ñ", "n").split()
    sep = r.choice([".", "_"])
    return sep.join(parts).replace(" ", "")
