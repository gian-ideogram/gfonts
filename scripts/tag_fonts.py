#!/usr/bin/env python3
"""Assign aesthetic and use-case tags to every font in the catalog.

Tags are derived from:
  1. Visual classification of each font via rendered contact sheets
  2. Category-based defaults
  3. Font-name pattern matching

Run:  python scripts/tag_fonts.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "gfonts" / "data"

# ── Tag vocabulary ────────────────────────────────────────────────────
# Aesthetic: elegant, playful, retro, modern, minimal, bold, quirky,
#            formal, casual, geometric, organic, technical, decorative,
#            high-contrast, rounded, angular, condensed, wide,
#            handwritten, calligraphic, cursive
# Use-case: heading, body, logo, caption, editorial, UI, signage, branding

# ── 1. Tag → font mappings (visual classification) ───────────────────
# Each tag maps to the set of font families that carry it, based on
# rendered contact-sheet review of all 1,709 catalog fonts.

TAG_GROUPS: dict[str, list[str]] = {
    # ── Aesthetic tags ────────────────────────────────────────────────

    "elegant": [
        "Abril Fatface", "Alegreya", "Alegreya SC", "Alice", "Alike",
        "Alike Angular", "Almendra", "Almendra Display", "Almendra SC",
        "Amethysta", "Ancizar Serif", "Andada Pro", "Antic Didone",
        "Arapey", "Baskervville", "Baskervville SC", "Bellefair",
        "Bodoni Moda", "Bodoni Moda SC", "Bona Nova", "Bona Nova SC",
        "Brygada 1918", "Cactus Classical Serif", "Cinzel",
        "Cinzel Decorative", "Cormorant", "Cormorant Garamond",
        "Cormorant Infant", "Cormorant SC", "Cormorant Unicase",
        "Cormorant Upright", "Crimson Pro", "Crimson Text",
        "DM Serif Display", "DM Serif Text", "EB Garamond",
        "Elsie", "Elsie Swash Caps", "Fanwood Text", "Faustina",
        "Fraunces", "Gabriela", "Gilda Display", "GFS Didot",
        "Goudy Bookletter 1911", "Hahmlet", "Ibarra Real Nova",
        "IM Fell Double Pica", "IM Fell DW Pica", "IM Fell English",
        "IM Fell French Canon", "IM Fell Great Primer",
        "Instrument Serif", "Kalnia", "Libre Baskerville",
        "Libre Bodoni", "Libre Caslon Display", "Libre Caslon Text",
        "Lora", "Newsreader", "Old Standard TT", "Oranienbaum",
        "Playfair", "Playfair Display", "Playfair Display SC",
        "Poltawski Nowy", "Prata", "Rosarivo", "Rufina",
        "Sorts Mill Goudy", "Spectral", "Spectral SC", "Vidaloka",
        "Vollkorn", "Vollkorn SC", "Wittgenstein", "Young Serif",
        "Della Respira", "Gloock", "Grandiflora One", "Joan",
        "Luxurious Roman", "Maname", "Marcellus", "Marcellus SC",
        "Piazzolla", "Platypi", "Sedan", "Sedan SC", "Solway",
        "Castoro", "Castoro Titling",
    ],

    "playful": [
        "ABeeZee", "Balsamiq Sans", "Baloo 2", "Baloo Bhai 2",
        "Baloo Bhaijaan 2", "Baloo Bhaina 2", "Baloo Chettan 2",
        "Baloo Da 2", "Baloo Paaji 2", "Baloo Tamma 2",
        "Baloo Tammudu 2", "Baloo Thambi 2", "Bangers",
        "Bubblegum Sans", "Cherry Bomb One", "Cherry Cream Soda",
        "Chewy", "Coiny", "Comic Neue", "Comic Relief",
        "DynaPuff", "Fredoka", "Fuzzy Bubbles", "Gochi Hand",
        "Grandstander", "Happy Monkey", "Indie Flower",
        "Itim", "Kalam", "Leckerli One", "Luckiest Guy",
        "Pangolin", "Patrick Hand", "Patrick Hand SC",
        "Playpen Sans", "Schoolbell", "Shantell Sans",
        "Short Stack", "Sniglet", "Tsukimi Rounded",
        "Boogaloo", "Bowlby One", "Caveat", "Caveat Brush",
        "Delius", "Delius Swash Caps", "Delius Unicase",
        "Handlee", "Just Another Hand", "Love Ya Like A Sister",
        "Mali", "McLaren", "Neucha", "Reenie Beanie",
        "Sriracha", "Sue Ellen Francisco", "Walter Turncoat",
        "Architects Daughter", "Coming Soon", "Crafty Girls",
        "Gloria Hallelujah", "Nothing You Could Do",
        "Over the Rainbow", "Shadows Into Light",
        "Shadows Into Light Two", "Swanky and Moo Moo",
        "The Girl Next Door", "Waiting for the Sunrise",
        "Give You Glory", "Loved by the King", "Madimi One",
        "Capriola", "Bellota", "Bellota Text", "Nerko One",
    ],

    "retro": [
        "Alfa Slab One", "Arvo", "Bungee", "Bungee Hairline",
        "Bungee Inline", "Bungee Outline", "Bungee Shade",
        "Codystar", "Graduate", "Limelight", "Monoton",
        "Nixie One", "Nosifer", "Orbitron", "Press Start 2P",
        "Righteous", "Rye", "Sancreek", "Special Elite",
        "Stardos Stencil", "Trade Winds", "VT323", "Wallpoet",
        "Vast Shadow", "Wellfleet", "Yeseva One", "Ewert",
        "Holtwood One SC", "Fontdiner Swanky", "UnifrakturMaguntia",
        "Kelly Slab", "Bowlby One SC", "Baumans", "Forum",
        "Germania One", "Glass Antiqua", "Gravitas One",
        "Modern Antiqua", "Poiret One", "Ruslan Display",
        "Sirin Stencil", "Uncial Antiqua", "Pirata One",
        "MedievalSharp", "Macondo", "Macondo Swash Caps",
        "New Rocker", "Oldenburg", "Grenze Gotisch",
        "Caesar Dressing", "Fondamento", "Felipa",
        "Silkscreen", "Pixelify Sans", "Jersey 20",
    ],

    "modern": [
        "Afacad", "Afacad Flux", "Albert Sans", "AR One Sans",
        "Archivo", "Archivo Narrow", "Barlow", "Be Vietnam Pro",
        "Bricolage Grotesque", "Cabin", "Cal Sans", "Carlito",
        "Catamaran", "Chivo", "Comme", "Commissioner", "DM Sans",
        "Encode Sans", "Epilogue", "Familjen Grotesk", "Figtree",
        "Fira Sans", "Funnel Sans", "Gantari", "Geist",
        "Geologica", "Georama", "Golos Text", "Google Sans",
        "Google Sans Flex", "Hanken Grotesk", "Heebo", "Hind",
        "Host Grotesk", "Hubot Sans", "IBM Plex Sans",
        "Instrument Sans", "Inter", "Inter Tight", "Jost",
        "Karla", "League Spartan", "Lexend", "Lexend Deca",
        "Lexend Exa", "Lexend Giga", "Lexend Mega", "Lexend Peta",
        "Lexend Tera", "Lexend Zetta", "Lato", "Libre Franklin",
        "Manrope", "Mona Sans", "Montserrat", "Mulish",
        "Noto Sans", "Noto Sans Display", "Nunito", "Nunito Sans",
        "Onest", "Open Sans", "Outfit", "Overpass",
        "Plus Jakarta Sans", "Poppins", "Public Sans",
        "Quicksand", "Raleway", "Red Hat Display", "Red Hat Text",
        "Reddit Sans", "Reddit Sans Condensed", "Rethink Sans",
        "Roboto", "Roboto Flex", "Rubik", "Sora",
        "Source Sans 3", "Space Grotesk", "Ubuntu", "Ubuntu Sans",
        "Urbanist", "Varta", "Work Sans", "Wix Madefor Display",
        "Wix Madefor Text", "Schibsted Grotesk", "Geom",
        "Inclusive Sans", "Nata Sans", "Parkinsans", "SN Pro",
        "Spline Sans", "Winky Sans", "Winky Rough",
        "TikTok Sans", "Zalando Sans", "Zalando Sans Expanded",
        "Zalando Sans SemiExpanded", "Mozilla Headline",
        "Mozilla Text", "Momo Trust Sans", "Savate",
        "Amarna", "Ancizar Sans", "Elms Sans", "Epunda Sans",
        "Alan Sans", "Asta Sans", "Stack Sans Headline",
        "Stack Sans Text", "Special Gothic",
    ],

    "minimal": [
        "Albert Sans", "Archivo", "DM Sans", "Figtree", "Geist",
        "IBM Plex Sans", "Inter", "Inter Tight", "Karla", "Lato",
        "Libre Franklin", "Manrope", "Noto Sans", "Open Sans",
        "Outfit", "Public Sans", "Red Hat Text", "Roboto",
        "Source Sans 3", "Ubuntu Sans", "Work Sans", "Cabin",
        "Catamaran", "Commissioner", "Epilogue", "Mulish",
        "Nunito Sans", "Overpass", "Plus Jakarta Sans",
        "Rethink Sans", "Rubik", "Sora", "Space Grotesk",
        "Urbanist", "Heebo", "Hind", "Inclusive Sans",
    ],

    "bold": [
        "Alfa Slab One", "Anton", "Anton SC", "Archivo Black",
        "Bakbak One", "Bangers", "Bebas Neue", "Black Ops One",
        "Bowlby One", "Bowlby One SC", "Carter One", "Chango",
        "Concert One", "Fugaz One", "Goblin One", "Gravitas One",
        "Lilita One", "Luckiest Guy", "Passion One", "Patua One",
        "Paytone One", "Rammetto One", "Russo One", "Squada One",
        "Staatliches", "Titan One", "Ultra", "Bungee",
        "Abril Fatface", "Calistoga", "Fredericka the Great",
        "Freeman", "Gajraj One", "Gasoek One", "Hammersmith One",
        "Jockey One", "Orelega One", "Racing Sans One",
        "Righteous", "Rubik Mono One", "Saira Stencil One",
        "Secular One", "Sigmar", "Sigmar One", "Shrikhand",
        "Teko", "Vina Sans", "Poetsen One", "Braah One",
        "Modak", "Mogra",
    ],

    "quirky": [
        "Audiowide", "Butcherman", "Cabin Sketch", "Cherry Bomb One",
        "Creepster", "Eater", "Ewert", "Fascinate", "Fascinate Inline",
        "Flavors", "Freckle Face", "Frijole", "Griffy",
        "Henny Penny", "Irish Grover", "Jolly Lodger", "Kranky",
        "Lacquer", "Margarine", "Metal Mania", "MedievalSharp",
        "Modak", "Mystery Quest", "Nosifer", "Pirata One",
        "Plaster", "Rock 3D", "Shojumaru", "Smokum",
        "Snowburst One", "Vampiro One", "Unkempt", "Slackey",
        "Akronim", "Barriecito", "Barrio", "Bungee Shade",
        "Chicle", "Emilys Candy", "Galindo", "Hanalei",
        "Hanalei Fill", "Iceberg", "Jolly Lodger", "Kenia",
        "Londrina Sketch", "Metal", "Miltonian Tattoo",
        "Mogra", "Moo Lah Lah", "Mountains of Christmas",
        "Paprika", "Purple Purse", "Ribeye", "Ribeye Marrow",
        "Risque", "Sarina", "Sevillana", "Spicy Rice",
        "Uncial Antiqua", "Unlock", "Vibes",
        "Protest Guerrilla", "Protest Revolution", "Protest Riot",
        "Protest Strike", "Road Rage", "Sekuya",
    ],

    "formal": [
        "Alegreya", "Alegreya SC", "Baskervville", "Baskervville SC",
        "Bodoni Moda", "Bodoni Moda SC", "Cardo", "Charis SIL",
        "Cormorant Garamond", "Crimson Pro", "Crimson Text",
        "EB Garamond", "Gentium Book Plus", "Gentium Plus",
        "GFS Didot", "Libre Baskerville", "Libre Bodoni",
        "Libre Caslon Text", "Literata", "Lora", "Merriweather",
        "Newsreader", "Noto Serif", "Noto Serif Display",
        "Old Standard TT", "Petrona", "PT Serif", "PT Serif Caption",
        "Roboto Serif", "Source Serif 4", "Spectral", "Spectral SC",
        "STIX Two Text", "Volkhov", "Vollkorn", "Vollkorn SC",
        "IBM Plex Serif", "Domine", "Gelasio", "Hepta Slab",
        "Kameron", "Rokkitt", "Bitter", "Besley",
        "Brygada 1918", "Frank Ruhl Libre", "Inknut Antiqua",
        "Noticia Text", "Quattrocento", "Tinos",
    ],

    "casual": [
        "ABeeZee", "Balsamiq Sans", "Cabin", "Comic Neue",
        "Comic Relief", "Delius", "Gochi Hand", "Handlee",
        "Indie Flower", "Just Another Hand", "Kalam", "Mali",
        "Patrick Hand", "Patrick Hand SC", "Permanent Marker",
        "Rock Salt", "Schoolbell", "Short Stack",
        "Shadows Into Light", "Shadows Into Light Two",
        "Yellowtail", "Annie Use Your Telescope",
        "Architects Daughter", "Caveat", "Caveat Brush",
        "Cedarville Cursive", "Coming Soon", "Covered By Your Grace",
        "Crafty Girls", "Dawning of a New Day", "Gloria Hallelujah",
        "Homemade Apple", "Just Me Again Down Here",
        "La Belle Aurore", "Loved by the King",
        "Neucha", "Nothing You Could Do", "Over the Rainbow",
        "Reenie Beanie", "Sedgwick Ave", "Sedgwick Ave Display",
        "Sue Ellen Francisco", "Swanky and Moo Moo",
        "The Girl Next Door", "Waiting for the Sunrise",
        "Walter Turncoat", "Give You Glory", "Itim",
        "Pangolin", "Sriracha", "Nerko One",
        "Fuzzy Bubbles", "Playpen Sans",
    ],

    "geometric": [
        "Comfortaa", "DM Sans", "Fredoka", "Geo", "Geologica",
        "Geom", "Josefin Sans", "Josefin Slab", "Jost",
        "League Spartan", "Maven Pro", "Montserrat",
        "Montserrat Alternates", "Montserrat Underline",
        "Nunito", "Outfit", "Poppins", "Quicksand", "Raleway",
        "Rubik", "Sora", "Space Grotesk", "Urbanist",
        "Varela Round", "Varela", "Albert Sans", "Figtree",
        "Manrope", "Mona Sans", "Plus Jakarta Sans", "Lexend",
        "Lexend Deca", "Red Hat Display", "Red Hat Text",
        "Rethink Sans", "Bricolage Grotesque",
        "Poiret One", "Julius Sans One", "Sulphur Point",
        "Tenor Sans", "Italiana", "GFS Neohellenic",
        "Didact Gothic", "Questrial",
    ],

    "organic": [
        "Amatic SC", "Architects Daughter", "Bad Script",
        "Calligraffitti", "Caveat", "Caveat Brush",
        "Cedarville Cursive", "Coming Soon", "Covered By Your Grace",
        "Crafty Girls", "Dancing Script", "Dawning of a New Day",
        "Delicious Handrawn", "Finger Paint", "Fuzzy Bubbles",
        "Give You Glory", "Gloria Hallelujah", "Gochi Hand",
        "Grape Nuts", "Handlee", "Homemade Apple", "Indie Flower",
        "Just Another Hand", "Just Me Again Down Here",
        "Kalam", "La Belle Aurore", "Loved by the King",
        "Mali", "Mansalva", "Neucha", "Nothing You Could Do",
        "Over the Rainbow", "Pangolin", "Patrick Hand",
        "Patrick Hand SC", "Permanent Marker",
        "Reenie Beanie", "Rock Salt", "Schoolbell",
        "Sedgwick Ave", "Short Stack",
        "Shadows Into Light", "Shadows Into Light Two",
        "Sue Ellen Francisco", "Sunshiney",
        "Swanky and Moo Moo", "The Girl Next Door",
        "Waiting for the Sunrise", "Walter Turncoat",
        "Annie Use Your Telescope", "Beth Ellen",
    ],

    "technical": [
        "Anonymous Pro", "Azeret Mono", "B612 Mono",
        "Cascadia Code", "Cascadia Mono", "Chivo Mono",
        "Courier Prime", "Cousine", "Cutive Mono", "Datatype",
        "DM Mono", "Fira Code", "Fira Mono", "Fragment Mono",
        "Geist Mono", "Google Sans Code", "IBM Plex Mono",
        "Inconsolata", "Intel One Mono", "Iosevka Charon",
        "Iosevka Charon Mono", "JetBrains Mono", "Kode Mono",
        "Lekton", "Libertinus Mono", "Lilex", "M PLUS 1 Code",
        "Major Mono Display", "Martian Mono", "Noto Sans Mono",
        "Nova Mono", "Overpass Mono", "Oxygen Mono", "PT Mono",
        "Red Hat Mono", "Reddit Mono", "Roboto Mono",
        "Share Tech Mono", "Sometype Mono", "Source Code Pro",
        "Space Mono", "Spline Sans Mono", "Syne Mono",
        "Ubuntu Mono", "Ubuntu Sans Mono", "Victor Mono",
        "VT323", "Xanh Mono", "Libertinus Mono",
        "B612", "Share Tech", "Electrolize", "Chakra Petch",
        "Rajdhani", "Orbitron", "Teko", "Oxanium",
        "Bruno Ace", "Bruno Ace SC", "Audiowide",
        "SUSE Mono",
    ],

    "decorative": [
        "Abril Fatface", "Akronim", "Alfa Slab One",
        "Almendra Display", "Asset", "Astloch", "Atomic Age",
        "Aubrey", "Averia Gruesa Libre", "Bagel Fat One",
        "Bahiana", "Bahianita", "Bangers", "Barriecito", "Barrio",
        "Bigelow Rules", "Bigshot One", "Black Ops One",
        "Boogaloo", "Bubblegum Sans", "Bungee", "Bungee Inline",
        "Bungee Shade", "Butcherman", "Caesar Dressing",
        "Ceviche One", "Cherry Bomb One", "Cherry Cream Soda",
        "Cherry Swash", "Chicle", "Cinzel Decorative",
        "Creepster", "Croissant One", "Crushed",
        "Diplomata", "Diplomata SC", "Dynalight",
        "Eater", "Emblema One", "Emilys Candy", "Erica One",
        "Ewert", "Exile", "Fascinate", "Fascinate Inline",
        "Faster One", "Flavors", "Flamenco", "Frijole",
        "Fruktur", "Galindo", "Germania One", "Girassol",
        "Glass Antiqua", "Goldman", "Gorditas", "Griffy",
        "Gugi", "Hanalei", "Hanalei Fill", "Henny Penny",
        "Iceberg", "Iceland", "Irish Grover", "Jolly Lodger",
        "Kenia", "Kranky", "Lacquer", "Lemon", "Limelight",
        "Lobster", "Lobster Two", "Londrina Outline",
        "Londrina Shadow", "Londrina Sketch", "Londrina Solid",
        "Margarine", "MedievalSharp", "Metal", "Metal Mania",
        "Milonga", "Miltonian Tattoo", "Miniver",
        "Modak", "Moirai One", "Monoton", "Moo Lah Lah",
        "Mountains of Christmas", "Mystery Quest",
        "New Rocker", "Nosifer", "Oleo Script",
        "Oleo Script Swash Caps", "Original Surfer",
        "Paprika", "Pirata One", "Plaster",
        "Press Start 2P", "Purple Purse", "Ranchers",
        "Rammetto One", "Ribeye", "Ribeye Marrow",
        "Rock 3D", "Rye", "Sail", "Sancreek",
        "Seaweed Script", "Shojumaru", "Sigmar", "Sigmar One",
        "Silkscreen", "Slackey", "Smokum", "Snowburst One",
        "Sofadi One", "Sonsie One", "Spicy Rice",
        "Spirax", "Squada One", "Trade Winds",
        "Uncial Antiqua", "UnifrakturMaguntia", "Unlock",
        "Vampiro One", "Vina Sans", "Wallpoet", "Wellfleet",
        "Yeseva One",
    ],

    "high-contrast": [
        "Abril Fatface", "Antic Didone", "Bodoni Moda",
        "Bodoni Moda SC", "Cormorant", "Cormorant Garamond",
        "Cormorant Infant", "Cormorant SC", "Cormorant Unicase",
        "Cormorant Upright", "DM Serif Display", "DM Serif Text",
        "Fraunces", "GFS Didot", "Gilda Display", "Newsreader",
        "Oranienbaum", "Playfair", "Playfair Display",
        "Playfair Display SC", "Prata", "Rozha One", "Ultra",
        "Vidaloka", "Yeseva One", "Libre Bodoni",
        "Libre Caslon Display", "Old Standard TT",
        "Piazzolla", "Rufina", "Spectral", "Spectral SC",
        "Young Serif", "Sorts Mill Goudy",
    ],

    "rounded": [
        "ABeeZee", "Comfortaa", "Fredoka", "M PLUS Rounded 1c",
        "Nunito", "Quicksand", "Tsukimi Rounded", "Varela Round",
        "Lexend", "Lexend Deca", "Lexend Exa", "Lexend Giga",
        "Lexend Mega", "Lexend Peta", "Lexend Tera", "Lexend Zetta",
        "Dongle", "Sniglet", "Baloo 2", "DynaPuff", "Mali",
        "Capriola", "Monda", "Nunito Sans", "Rubik",
        "Cabin", "Ubuntu", "Ubuntu Sans", "Varela",
        "Maven Pro", "Sour Gummy", "Madimi One",
    ],

    "angular": [
        "Orbitron", "Rajdhani", "Teko", "Chakra Petch",
        "Electrolize", "Michroma", "Share Tech", "Syncopate",
        "Quantico", "Aldrich", "Bruno Ace", "Bruno Ace SC",
        "Coda", "Oxanium", "Turret Road", "Iceland",
        "Jura", "Exo", "Exo 2", "K2D", "Tomorrow",
        "Armata", "Dosis", "Russo One", "Share", "Strait",
        "Bai Jamjuree", "KoHo", "Kodchasan", "Fahkwang",
        "Krub", "Prompt", "Niramit", "Sarabun",
    ],

    "condensed": [
        "Abel", "Antonio", "Barlow Condensed", "Barlow Semi Condensed",
        "Bebas Neue", "BenchNine", "Cabin Condensed",
        "Encode Sans Condensed", "Encode Sans Semi Condensed",
        "Fira Sans Condensed", "Fira Sans Extra Condensed",
        "IBM Plex Sans Condensed", "League Gothic", "Oswald",
        "Pathway Gothic One", "PT Sans Narrow", "Roboto Condensed",
        "Saira Condensed", "Saira Extra Condensed",
        "Saira Semi Condensed", "Six Caps", "Sofia Sans Condensed",
        "Sofia Sans Extra Condensed", "Sofia Sans Semi Condensed",
        "Special Gothic Condensed One", "Asap Condensed",
        "Yanone Kaffeesatz", "Wire One", "Fjalla One", "Dorsa",
        "Strait", "Stint Ultra Condensed", "Alumni Sans",
        "Economica", "Francois One", "Georama", "Genos",
        "Homenaje", "Pathway Extreme", "Reddit Sans Condensed",
        "Ropa Sans", "Tulpen One", "News Cycle",
    ],

    "wide": [
        "Advent Pro", "BioRhyme Expanded", "Encode Sans Expanded",
        "Encode Sans Semi Expanded", "Sofia Sans",
        "Special Gothic Expanded One", "Stint Ultra Expanded",
        "BhuTuka Expanded One", "Padyakke Expanded One",
        "Seymour One", "Rubik Mono One", "Syncopate",
        "Allerta Stencil", "Michroma", "Orbitron",
        "Squada One", "Bowlby One", "Bowlby One SC",
        "Zalando Sans Expanded",
    ],

    "handwritten": [
        "Amatic SC", "Amita", "Annie Use Your Telescope",
        "Architects Daughter", "Are You Serious", "Beth Ellen",
        "Betania Patmos", "Betania Patmos In", "Bonbon", "Borel",
        "Calligraffitti", "Cause", "Caveat", "Caveat Brush",
        "Cedarville Cursive", "Chilanka", "Comic Neue", "Coming Soon",
        "Covered By Your Grace", "Crafty Girls", "Dawning of a New Day",
        "Dekko", "Delicious Handrawn", "Delius", "Delius Swash Caps",
        "Delius Unicase", "Edu AU VIC WA NT Hand", "Edu AU VIC WA NT Pre",
        "Edu NSW ACT Cursive", "Edu NSW ACT Foundation",
        "Edu NSW ACT Hand Pre", "Edu QLD Beginner", "Edu QLD Hand",
        "Edu SA Beginner", "Edu SA Hand", "Edu TAS Beginner",
        "Edu VIC WA NT Beginner", "Edu VIC WA NT Hand",
        "Edu VIC WA NT Hand Pre", "Fuggles", "Fuzzy Bubbles",
        "Give You Glory", "Gloria Hallelujah", "Gochi Hand",
        "Grape Nuts", "Gveret Levin", "Handlee", "Homemade Apple",
        "Indie Flower", "Itim", "Julee", "Just Another Hand",
        "Just Me Again Down Here", "Kalam", "Kapakana", "Kavivanar",
        "Klee One", "La Belle Aurore", "Lakki Reddy",
        "Loved by the King", "Lugrasimo", "Lumanosimo", "Mali",
        "Mansalva", "Meddon", "Mynerve", "Neonderthaw", "Nerko One",
        "Neucha", "Nothing You Could Do", "Ole", "Oooh Baby",
        "Over the Rainbow", "Pangolin", "Patrick Hand",
        "Patrick Hand SC", "Permanent Marker", "Playpen Sans",
        "Puppies Play", "Reenie Beanie", "Rock Salt", "Ruge Boogie",
        "Schoolbell", "Sedgwick Ave", "Sedgwick Ave Display",
        "Shadows Into Light", "Shadows Into Light Two",
        "Short Stack", "Smooch", "Sofia", "Sriracha",
        "Sue Ellen Francisco", "Sunshiney", "Swanky and Moo Moo",
        "The Girl Next Door", "Twinkle Star", "Vibur",
        "Waiting for the Sunrise", "Walter Turncoat", "Zeyada",
        "Shantell Sans", "Balsamiq Sans", "Comic Relief",
    ],

    "calligraphic": [
        "Aguafina Script", "Alex Brush", "Allison", "Allura",
        "Arizonia", "Ballet", "Beau Rivage", "Berkshire Swash",
        "Bilbo", "Bilbo Swash Caps", "Birthstone", "Birthstone Bounce",
        "Bonheur Royale", "Butterfly Kids", "Carattere", "Cherish",
        "Clicker Script", "Condiment", "Corinthia", "Devonshire",
        "Dr Sugiyama", "Eagle Lake", "Engagement", "Ephesis",
        "Estonia", "Euphoria Script", "Explora", "Felipa",
        "Festive", "Fleur De Leah", "Fondamento", "Great Vibes",
        "Grechen Fuemen", "Grey Qo", "Gwendolyn",
        "Herr Von Muellerhoff", "Hurricane", "Imperial Script",
        "Ingrid Darling", "Inspiration", "Island Moments",
        "Italianno", "Jim Nightshade", "Kings", "Kolker Brush",
        "Kristi", "Lavishly Yours", "League Script", "Licorice",
        "Love Light", "Lovers Quarrel", "Luxurious Script",
        "Mea Culpa", "Meie Script", "Meow Script",
        "Miss Fajardose", "Molle", "Monsieur La Doulaise",
        "MonteCarlo", "Moon Dance", "Mr Bedfort", "Mr Dafoe",
        "Mr De Haviland", "Mrs Saint Delafield", "Mrs Sheppards",
        "Ms Madi", "My Soul", "Parisienne", "Passions Conflict",
        "Petemoss", "Petit Formal Script", "Pinyon Script",
        "Praise", "Princess Sofia", "Quintessential", "Qwigley",
        "Qwitcher Grypen", "Rochester", "Romanesco", "Rouge Script",
        "Ruthie", "Sacramento", "Sassy Frass", "Send Flowers",
        "Shalimar", "Splash", "Square Peg", "Stalemate",
        "Style Script", "Tangerine", "Tapestry", "The Nautigal",
        "Updock", "Vujahday Script", "Water Brush", "Waterfall",
        "Whisper", "WindSong", "Seaweed Script",
    ],

    "cursive": [
        "Aguafina Script", "Alex Brush", "Allison", "Allura",
        "Arizonia", "Babylonica", "Bad Script", "Caramel",
        "Carattere", "Charm", "Charmonman", "Clicker Script",
        "Comforter", "Comforter Brush", "Cookie", "Corinthia",
        "Courgette", "Damion", "Dancing Script", "Grand Hotel",
        "Great Vibes", "Hurricane", "Italianno", "Kaushan Script",
        "Leckerli One", "Lobster", "Lobster Two", "Marck Script",
        "Merienda", "Montez", "Niconne", "Norican", "Pacifico",
        "Parisienne", "Rancho", "Redressed", "Rochester",
        "Sacramento", "Satisfy", "Style Script", "Yellowtail",
        "Yesteryear", "Birthstone", "Bonheur Royale",
        "Ephesis", "Euphoria Script", "Fleur De Leah",
        "Gwendolyn", "Imperial Script", "Kings",
        "Lavishly Yours", "Love Light", "Luxurious Script",
        "MonteCarlo", "Moon Dance", "Mr Dafoe",
        "Mr De Haviland", "Mrs Saint Delafield",
        "Petit Formal Script", "Pinyon Script", "Qwitcher Grypen",
        "Rouge Script", "Shalimar", "Tangerine",
        "The Nautigal", "Updock", "Water Brush", "Waterfall",
        "WindSong", "Lily Script One", "Oleo Script",
        "Oleo Script Swash Caps", "Playball",
    ],

    # ── Use-case tags ─────────────────────────────────────────────────

    "heading": [
        "Abril Fatface", "Alfa Slab One", "Anton", "Anton SC",
        "Archivo Black", "Bangers", "Bebas Neue", "Big Shoulders",
        "Big Shoulders Inline", "Big Shoulders Stencil",
        "Black Ops One", "Bungee", "Calistoga", "Carter One",
        "Changa One", "Chango", "Cinzel", "Concert One",
        "DM Serif Display", "Freeman", "Fugaz One", "Gajraj One",
        "Goldman", "Graduate", "Josefin Sans", "Limelight",
        "Lilita One", "Lobster", "Lora", "Luckiest Guy",
        "Merriweather", "Montserrat", "Oswald", "Passion One",
        "Patua One", "Paytone One", "Playfair Display",
        "Playfair Display SC", "Poppins", "Raleway",
        "Rammetto One", "Red Hat Display", "Righteous",
        "Rubik Mono One", "Russo One", "Sigmar", "Squada One",
        "Staatliches", "Titan One", "Ultra", "Yeseva One",
        "Bodoni Moda", "Cormorant", "DM Sans", "Fjalla One",
        "Fraunces", "IBM Plex Serif", "Instrument Serif",
        "League Gothic", "League Spartan", "Libre Baskerville",
        "Noto Serif Display", "Old Standard TT", "Outfit",
        "Piazzolla", "Prata", "Source Serif 4", "Spectral",
        "Vollkorn", "Wittgenstein", "Young Serif",
        "Funnel Display", "Gabarito", "Sora",
        "Archivo", "Barlow", "Jost", "Manrope", "Urbanist",
    ],

    "body": [
        "Alegreya", "Archivo", "Asap", "Bitter", "Cabin",
        "Caladea", "Carlito", "Charis SIL", "Chivo", "Crimson Pro",
        "Crimson Text", "DM Sans", "EB Garamond", "Fira Sans",
        "Gelasio", "Gentium Book Plus", "Gentium Plus",
        "IBM Plex Sans", "IBM Plex Serif", "Inter", "Inter Tight",
        "Karla", "Lato", "Libre Baskerville", "Libre Caslon Text",
        "Libre Franklin", "Literata", "Lora", "Merriweather",
        "Mulish", "Noto Sans", "Noto Serif", "Nunito",
        "Nunito Sans", "Open Sans", "Overpass", "PT Sans",
        "PT Serif", "Public Sans", "Roboto", "Roboto Serif",
        "Roboto Slab", "Rubik", "Source Sans 3", "Source Serif 4",
        "Spectral", "Tinos", "Ubuntu", "Ubuntu Sans",
        "Vollkorn", "Work Sans", "Heebo", "Hind", "Mukta",
        "Poppins", "Raleway", "Red Hat Text", "Manrope",
        "Figtree", "Plus Jakarta Sans", "Outfit",
        "Newsreader", "Petrona", "Piazzolla", "Faustina",
        "Inria Sans", "Inria Serif", "Assistant", "Catamaran",
        "Commissioner", "Encode Sans", "Epilogue", "Georama",
        "Golos Text", "Rethink Sans", "Urbanist",
        "Atkinson Hyperlegible", "Atkinson Hyperlegible Next",
        "Inclusive Sans", "Andika", "Cantarell",
    ],

    "logo": [
        "Abril Fatface", "Bangers", "Bebas Neue", "Bungee",
        "Comfortaa", "Fredoka", "Goldman", "Josefin Sans",
        "Lobster", "Montserrat", "Orbitron", "Pacifico",
        "Permanent Marker", "Playfair Display", "Poppins",
        "Quicksand", "Raleway", "Righteous", "Rubik Mono One",
        "Staatliches", "Audiowide", "Black Ops One",
        "Poiret One", "Syncopate", "Teko", "Michroma",
        "Monoton", "Russo One", "Titan One", "Alfa Slab One",
        "Cinzel", "Ostwald", "Racing Sans One", "Fredericka the Great",
        "Luckiest Guy",
    ],

    "caption": [
        "IBM Plex Sans", "Inter", "Noto Sans", "Open Sans",
        "PT Sans", "PT Sans Caption", "Roboto", "Source Sans 3",
        "Work Sans", "DM Sans", "Fira Sans", "Libre Franklin",
        "Mulish", "Nunito Sans", "Public Sans", "Ubuntu Sans",
        "Lato", "Karla", "Red Hat Text",
        "Atkinson Hyperlegible", "Atkinson Hyperlegible Next",
    ],

    "editorial": [
        "Alegreya", "Bodoni Moda", "Bodoni Moda SC",
        "Cormorant Garamond", "Crimson Pro", "Crimson Text",
        "EB Garamond", "Fraunces", "Libre Baskerville",
        "Libre Bodoni", "Libre Caslon Text", "Literata",
        "Lora", "Merriweather", "Newsreader", "Noto Serif",
        "Noto Serif Display", "Playfair Display",
        "Playfair Display SC", "Source Serif 4", "Spectral",
        "Spectral SC", "Vollkorn", "Vollkorn SC",
        "Old Standard TT", "Piazzolla", "Petrona",
        "Andada Pro", "Faustina", "Frank Ruhl Libre",
        "IBM Plex Serif", "Inknut Antiqua", "Noticia Text",
        "Wittgenstein",
    ],

    "UI": [
        "DM Sans", "Figtree", "Geist", "IBM Plex Sans", "Inter",
        "Inter Tight", "Lato", "Noto Sans", "Open Sans",
        "Poppins", "Roboto", "Source Sans 3", "Ubuntu",
        "Ubuntu Sans", "Work Sans", "Red Hat Text", "Outfit",
        "Public Sans", "Nunito Sans", "Manrope", "Rubik",
        "Plus Jakarta Sans", "Mulish", "Karla", "Cabin",
        "Fira Sans", "Libre Franklin", "Overpass", "PT Sans",
        "Catamaran", "Commissioner", "Encode Sans",
        "Heebo", "Hind", "Lexend", "Lexend Deca",
        "Atkinson Hyperlegible", "Atkinson Hyperlegible Next",
        "Reddit Sans", "Rethink Sans", "Inclusive Sans",
        "Google Sans", "Google Sans Flex",
    ],

    "signage": [
        "Anton", "Bebas Neue", "Big Shoulders",
        "Big Shoulders Stencil", "Bungee", "Montserrat",
        "Oswald", "Poppins", "Staatliches", "Teko",
        "Alfa Slab One", "Barlow", "Black Ops One",
        "Fjalla One", "League Gothic", "Lilita One",
        "Patua One", "Roboto Condensed", "Russo One",
        "Titillium Web", "National Park",
    ],

    "branding": [
        "Abril Fatface", "Bangers", "Bodoni Moda",
        "Comfortaa", "Josefin Sans", "Lobster",
        "Montserrat", "Orbitron", "Pacifico",
        "Permanent Marker", "Playfair Display", "Poppins",
        "Quicksand", "Raleway", "Righteous", "Roboto",
        "Fredoka", "Goldman", "Poiret One", "Urbanist",
        "Sora", "Space Grotesk", "Work Sans", "Lato",
        "DM Sans", "Inter",
    ],
}


# ── 2. Category-based default tags ────────────────────────────────────
# Applied to every font unless overridden by explicit tag groups.
CATEGORY_DEFAULTS: dict[str, list[str]] = {
    "Serif": ["formal"],
    "Sans Serif": ["modern"],
    "Display": ["heading", "decorative"],
    "Handwriting": ["casual", "organic"],
    "Monospace": ["technical"],
    "Unknown": ["decorative"],
}


# ── 3. Name-pattern rules (additive) ─────────────────────────────────
NAME_PATTERN_TAGS: list[tuple[str, list[str]]] = [
    ("condensed", ["condensed"]),
    ("narrow", ["condensed"]),
    ("expanded", ["wide"]),
    ("wide", ["wide"]),
    ("mono", ["technical"]),
    ("rounded", ["rounded"]),
    ("slab", []),
    ("display", ["heading"]),
    ("sc", []),
    ("stencil", ["decorative"]),
    ("inline", ["decorative"]),
    ("outline", ["decorative"]),
]


def invert_tag_groups(tag_groups: dict[str, list[str]]) -> dict[str, set[str]]:
    """Convert tag→fonts mapping to font→tags mapping."""
    result: dict[str, set[str]] = {}
    for tag, families in tag_groups.items():
        for family in families:
            result.setdefault(family, set()).add(tag)
    return result


def apply_name_patterns(family: str) -> set[str]:
    """Derive tags from font family name patterns."""
    tags: set[str] = set()
    name_lower = family.lower()
    for pattern, pattern_tags in NAME_PATTERN_TAGS:
        if pattern in name_lower:
            tags.update(pattern_tags)
    return tags


def tag_fonts(entries: list[dict], explicit_tags: dict[str, set[str]]) -> list[dict]:
    """Assign tags to a list of font entries."""
    for entry in entries:
        family = entry["family"]
        category = entry.get("category", "Unknown")

        tags: set[str] = set()

        # Layer 1: category defaults
        tags.update(CATEGORY_DEFAULTS.get(category, []))

        # Layer 2: name patterns
        tags.update(apply_name_patterns(family))

        # Layer 3: explicit visual classification (overrides/adds)
        if family in explicit_tags:
            tags.update(explicit_tags[family])

        entry["tags"] = sorted(tags)

    return entries


def main() -> None:
    explicit_tags = invert_tag_groups(TAG_GROUPS)

    # Process allowlist
    allow_path = DATA_DIR / "allowlist.json"
    allowlist = json.loads(allow_path.read_text())
    tag_fonts(allowlist, explicit_tags)
    allow_path.write_text(json.dumps(allowlist, indent=2, ensure_ascii=False) + "\n")

    # Process script fonts
    script_path = DATA_DIR / "script_fonts.json"
    script_fonts = json.loads(script_path.read_text())
    tag_fonts(script_fonts, explicit_tags)
    script_path.write_text(json.dumps(script_fonts, indent=2, ensure_ascii=False) + "\n")

    # Report stats
    all_fonts = allowlist + script_fonts
    total = len(all_fonts)
    tagged = sum(1 for f in all_fonts if f.get("tags"))
    untagged = total - tagged
    all_tags: set[str] = set()
    for f in all_fonts:
        all_tags.update(f.get("tags", []))

    print(f"Total fonts: {total}")
    print(f"  Tagged:   {tagged} ({tagged*100//total}%)")
    print(f"  Untagged: {untagged} ({untagged*100//total}%)")
    print(f"  Unique tags: {len(all_tags)}")
    print(f"  Tags: {sorted(all_tags)}")
    print()

    # Per-tag counts
    tag_counts: dict[str, int] = {}
    for f in all_fonts:
        for t in f.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    for tag in sorted(tag_counts, key=lambda t: -tag_counts[t]):
        print(f"  {tag:20s} {tag_counts[tag]:4d} fonts")


if __name__ == "__main__":
    main()
