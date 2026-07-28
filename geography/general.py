from __future__ import annotations

from enum import Enum

class Wojewodztwo(Enum):
    DOLNOSLASKIE = "dolnośląskie"
    KUJAWSKO_POMORSKIE = "kujawsko-pomorskie"
    LUBELSKIE = "lubelskie"
    LUBUSKIE = "lubuskie"
    LODZKIE = "łódzkie"
    MALOPOLSKIE = "małopolskie"
    MAZOWIECKIE = "mazowieckie"
    OPOLSKIE = "opolskie"
    PODKARPACKIE = "podkarpackie"
    PODLASKIE = "podlaskie"
    POMORSKIE = "pomorskie"
    SLASKIE = "śląskie"
    SWIETOKRZYSKIE = "świętokrzyskie"
    WARMINSKO_MAZURSKIE = "warmińsko-mazurskie"
    WIELKOPOLSKIE = "wielkopolskie"
    ZACHODNIOPOMORSKIE = "zachodniopomorskie"


class Podregion(Enum):
    # Dolnośląskie
    JELENIOGORSKI = "jeleniogórski"
    LEGNICKO_GLOGOWSKI = "legnicko-głogowski"
    WALBRZYSKI = "wałbrzyski"
    WROCLAWSKI = "wrocławski"
    MIASTO_WROCLAW = "miasto Wrocław"

    # Kujawsko-pomorskie
    BYDGOSKO_TORUNSKI = "bydgosko-toruński"
    GRUDZIADZKI = "grudziądzki"
    INOWROCLAWSKI = "inowrocławski"
    SWIECKI = "świecki"
    WLOCLAWSKI = "włocławski"

    # Lubelskie
    BIALSKI = "bialski"
    CHELMSKO_ZAMOJSKI = "chełmsko-zamojski"
    LUBELSKI = "lubelski"
    PULAWSKI = "puławski"

    # Lubuskie
    GORZOWSKI = "gorzowski"
    ZIELONOGORSKI = "zielonogórski"

    # Łódzkie
    LODZKI = "łódzki"
    MIASTO_LODZ = "miasto Łódź"
    PIOTRKOWSKI = "piotrkowski"
    SIERADZKI = "sieradzki"
    SKIERNIEWICKI = "skierniewicki"

    # Małopolskie
    KRAKOWSKI = "krakowski"
    MIASTO_KRAKOW = "miasto Kraków"
    NOWOSADECKI = "nowosądecki"
    NOWOTARSKI = "nowotarski"
    OSWIECIMSKI = "oświęcimski"
    TARNOWSKI = "tarnowski"

    # Mazowieckie
    CIECHANOWSKI = "ciechanowski"
    OSTROLECKI = "ostrołęcki"
    RADOMSKI = "radomski"
    PLOCKI = "płocki"
    SIEDLECKI = "siedlecki"
    ZYRARDOWSKI = "żyrardowski"
    MIASTO_WARSZAWA = "miasto Warszawa"
    WARSZAWSKI_WSCHODNI = "warszawski wschodni"
    WARSZAWSKI_ZACHODNI = "warszawski zachodni"

    # Opolskie
    NYSKI = "nyski"
    OPOLSKI = "opolski"

    # Podkarpackie
    KROSNIENSKI = "krośnieński"
    PRZEMYSKI = "przemyski"
    RZESZOWSKI = "rzeszowski"
    TARNOBRZESKI = "tarnobrzeski"

    # Podlaskie
    BIALOSTOCKI = "białostocki"
    LOMZYNSKI = "łomżyński"
    SUWALSKI = "suwalski"

    # Pomorskie
    CHOJNICKI = "chojnicki"
    GDANSKI = "gdański"
    STAROGARDZKI = "starogardzki"
    SLUPSKI = "słupski"
    TROJMIEJSKI = "trójmiejski"

    # Śląskie
    BIELSKI = "bielski"
    BYTOMSKI = "bytomski"
    CZESTOCHOWSKI = "częstochowski"
    GLIWICKI = "gliwicki"
    KATOWICKI = "katowicki"
    RYBNICKI = "rybnicki"
    SOSNOWIECKI = "sosnowiecki"
    TYSKI = "tyski"

    # Świętokrzyskie
    KIELECKI = "kielecki"
    SANDOMIERSKO_JEDRZEJOWSKI = "sandomiersko-jędrzejowski"

    # Warmińsko-mazurskie
    ELBLASKI = "elbląski"
    ELCKI = "ełcki"
    OLSZTYNSKI = "olsztyński"

    # Wielkopolskie
    KALISKI = "kaliski"
    KONINSKI = "koniński"
    LESZCZYNSKI = "leszczyński"
    PILSKI = "pilski"
    POZNANSKI = "poznański"
    MIASTO_POZNAN = "miasto Poznań"

    # Zachodniopomorskie
    KOSZALINSKI = "koszaliński"
    MIASTO_SZCZECIN = "miasto Szczecin"
    SZCZECINECKO_PYRZYCKI = "szczecinecko-pyrzycki"
    SZCZECINSKI = "szczeciński"


class Powiat(str, Enum):
    """Wszystkie powiaty i miasta na prawach powiatu w Polsce.

    ``value`` jest unikalnym kluczem tekstowym.
    ``label`` zawiera właściwą nazwę powiatu/miasta.
    ``wojewodztwo`` określa województwo.
    """

    def __new__(
            cls,
            label: str,
            wojewodztwo: str,
            is_city_county: bool = False,
    ):
        unit_type = "miasto" if is_city_county else "powiat"
        value = f"{wojewodztwo}|{unit_type}|{label}"
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label = label
        obj.wojewodztwo = wojewodztwo
        obj.is_city_county = is_city_county
        return obj

    @property
    def display_name(self) -> str:
        prefix = "miasto" if self.is_city_county else "powiat"
        return f"{prefix} {self.label}"

    @classmethod
    def for_wojewodztwo(cls, wojewodztwo: str) -> list["Powiat"]:
        return [item for item in cls if item.wojewodztwo == wojewodztwo]

    # Dolnośląskie
    DOLNOSLASKIE_BOLESLAWIECKI = ('bolesławiecki', 'dolnośląskie', False)
    DOLNOSLASKIE_DZIERZONIOWSKI = ('dzierżoniowski', 'dolnośląskie', False)
    DOLNOSLASKIE_GLOGOWSKI = ('głogowski', 'dolnośląskie', False)
    DOLNOSLASKIE_GOROWSKI = ('górowski', 'dolnośląskie', False)
    DOLNOSLASKIE_JAWORSKI = ('jaworski', 'dolnośląskie', False)
    DOLNOSLASKIE_KARKONOSKI = ('karkonoski', 'dolnośląskie', False)
    DOLNOSLASKIE_KAMIENNOGORSKI = ('kamiennogórski', 'dolnośląskie', False)
    DOLNOSLASKIE_KLODZKI = ('kłodzki', 'dolnośląskie', False)
    DOLNOSLASKIE_LEGNICKI = ('legnicki', 'dolnośląskie', False)
    DOLNOSLASKIE_LUBANSKI = ('lubański', 'dolnośląskie', False)
    DOLNOSLASKIE_LUBINSKI = ('lubiński', 'dolnośląskie', False)
    DOLNOSLASKIE_LWOWECKI = ('lwówecki', 'dolnośląskie', False)
    DOLNOSLASKIE_MILICKI = ('milicki', 'dolnośląskie', False)
    DOLNOSLASKIE_OLESNICKI = ('oleśnicki', 'dolnośląskie', False)
    DOLNOSLASKIE_OLAWSKI = ('oławski', 'dolnośląskie', False)
    DOLNOSLASKIE_POLKOWICKI = ('polkowicki', 'dolnośląskie', False)
    DOLNOSLASKIE_STRZELINSKI = ('strzeliński', 'dolnośląskie', False)
    DOLNOSLASKIE_SREDZKI = ('średzki', 'dolnośląskie', False)
    DOLNOSLASKIE_SWIDNICKI = ('świdnicki', 'dolnośląskie', False)
    DOLNOSLASKIE_TRZEBNICKI = ('trzebnicki', 'dolnośląskie', False)
    DOLNOSLASKIE_WALBRZYSKI = ('wałbrzyski', 'dolnośląskie', False)
    DOLNOSLASKIE_WOLOWSKI = ('wołowski', 'dolnośląskie', False)
    DOLNOSLASKIE_WROCLAWSKI = ('wrocławski', 'dolnośląskie', False)
    DOLNOSLASKIE_ZABKOWICKI = ('ząbkowicki', 'dolnośląskie', False)
    DOLNOSLASKIE_ZGORZELECKI = ('zgorzelecki', 'dolnośląskie', False)
    DOLNOSLASKIE_ZLOTORYJSKI = ('złotoryjski', 'dolnośląskie', False)
    DOLNOSLASKIE_MIASTO_JELENIA_GORA = ('Jelenia Góra', 'dolnośląskie', True)
    DOLNOSLASKIE_MIASTO_LEGNICA = ('Legnica', 'dolnośląskie', True)
    DOLNOSLASKIE_MIASTO_WALBRZYCH = ('Wałbrzych', 'dolnośląskie', True)
    DOLNOSLASKIE_MIASTO_WROCLAW = ('Wrocław', 'dolnośląskie', True)

    # Kujawsko-pomorskie
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI = ('aleksandrowski', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_BRODNICKI = ('brodnicki', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_BYDGOSKI = ('bydgoski', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_CHELMINSKI = ('chełmiński', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_GOLUBSKO_DOBRZYNSKI = ('golubsko-dobrzyński', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_GRUDZIADZKI = ('grudziądzki', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI = ('inowrocławski', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_LIPNOWSKI = ('lipnowski', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_MOGILENSKI = ('mogileński', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_NAKIELSKI = ('nakielski', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_RADZIEJOWSKI = ('radziejowski', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_RYPINSKI = ('rypiński', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_SEPOLENSKI = ('sępoleński', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_SWIECKI = ('świecki', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_TORUNSKI = ('toruński', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_TUCHOLSKI = ('tucholski', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_WABRZESKI = ('wąbrzeski', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_WLOCLAWSKI = ('włocławski', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_ZNINSKI = ('żniński', 'kujawsko-pomorskie', False)
    KUJAWSKO_POMORSKIE_MIASTO_BYDGOSZCZ = ('Bydgoszcz', 'kujawsko-pomorskie', True)
    KUJAWSKO_POMORSKIE_MIASTO_GRUDZIADZ = ('Grudziądz', 'kujawsko-pomorskie', True)
    KUJAWSKO_POMORSKIE_MIASTO_TORUN = ('Toruń', 'kujawsko-pomorskie', True)
    KUJAWSKO_POMORSKIE_MIASTO_WLOCLAWEK = ('Włocławek', 'kujawsko-pomorskie', True)

    # Lubelskie
    LUBELSKIE_BIALSKI = ('bialski', 'lubelskie', False)
    LUBELSKIE_BILGORAJSKI = ('biłgorajski', 'lubelskie', False)
    LUBELSKIE_CHELMSKI = ('chełmski', 'lubelskie', False)
    LUBELSKIE_HRUBIESZOWSKI = ('hrubieszowski', 'lubelskie', False)
    LUBELSKIE_JANOWSKI = ('janowski', 'lubelskie', False)
    LUBELSKIE_KRASNOSTAWSKI = ('krasnostawski', 'lubelskie', False)
    LUBELSKIE_KRASNICKI = ('kraśnicki', 'lubelskie', False)
    LUBELSKIE_LUBARTOWSKI = ('lubartowski', 'lubelskie', False)
    LUBELSKIE_LUBELSKI = ('lubelski', 'lubelskie', False)
    LUBELSKIE_LECZYNSKI = ('łęczyński', 'lubelskie', False)
    LUBELSKIE_LUKOWSKI = ('łukowski', 'lubelskie', False)
    LUBELSKIE_OPOLSKI = ('opolski', 'lubelskie', False)
    LUBELSKIE_PARCZEWSKI = ('parczewski', 'lubelskie', False)
    LUBELSKIE_PULAWSKI = ('puławski', 'lubelskie', False)
    LUBELSKIE_RADZYNSKI = ('radzyński', 'lubelskie', False)
    LUBELSKIE_RYCKI = ('rycki', 'lubelskie', False)
    LUBELSKIE_SWIDNICKI = ('świdnicki', 'lubelskie', False)
    LUBELSKIE_TOMASZOWSKI = ('tomaszowski', 'lubelskie', False)
    LUBELSKIE_WLODAWSKI = ('włodawski', 'lubelskie', False)
    LUBELSKIE_ZAMOJSKI = ('zamojski', 'lubelskie', False)
    LUBELSKIE_MIASTO_BIALA_PODLASKA = ('Biała Podlaska', 'lubelskie', True)
    LUBELSKIE_MIASTO_CHELM = ('Chełm', 'lubelskie', True)
    LUBELSKIE_MIASTO_LUBLIN = ('Lublin', 'lubelskie', True)
    LUBELSKIE_MIASTO_ZAMOSC = ('Zamość', 'lubelskie', True)

    # Lubuskie
    LUBUSKIE_GORZOWSKI = ('gorzowski', 'lubuskie', False)
    LUBUSKIE_KROSNIENSKI = ('krośnieński', 'lubuskie', False)
    LUBUSKIE_MIEDZYRZECKI = ('międzyrzecki', 'lubuskie', False)
    LUBUSKIE_NOWOSOLSKI = ('nowosolski', 'lubuskie', False)
    LUBUSKIE_SLUBICKI = ('słubicki', 'lubuskie', False)
    LUBUSKIE_STRZELECKO_DREZDENECKI = ('strzelecko-drezdenecki', 'lubuskie', False)
    LUBUSKIE_SULECINSKI = ('sulęciński', 'lubuskie', False)
    LUBUSKIE_SWIEBODZINSKI = ('świebodziński', 'lubuskie', False)
    LUBUSKIE_WSCHOWSKI = ('wschowski', 'lubuskie', False)
    LUBUSKIE_ZIELONOGORSKI = ('zielonogórski', 'lubuskie', False)
    LUBUSKIE_ZAGANSKI = ('żagański', 'lubuskie', False)
    LUBUSKIE_ZARSKI = ('żarski', 'lubuskie', False)
    LUBUSKIE_MIASTO_GORZOW_WIELKOPOLSKI = ('Gorzów Wielkopolski', 'lubuskie', True)
    LUBUSKIE_MIASTO_ZIELONA_GORA = ('Zielona Góra', 'lubuskie', True)

    # Łódzkie
    LODZKIE_BELCHATOWSKI = ('bełchatowski', 'łódzkie', False)
    LODZKIE_BRZEZINSKI = ('brzeziński', 'łódzkie', False)
    LODZKIE_KUTNOWSKI = ('kutnowski', 'łódzkie', False)
    LODZKIE_LASKI = ('łaski', 'łódzkie', False)
    LODZKIE_LECZYCKI = ('łęczycki', 'łódzkie', False)
    LODZKIE_LOWICKI = ('łowicki', 'łódzkie', False)
    LODZKIE_LODZKI_WSCHODNI = ('łódzki wschodni', 'łódzkie', False)
    LODZKIE_OPOCZYNSKI = ('opoczyński', 'łódzkie', False)
    LODZKIE_PABIANICKI = ('pabianicki', 'łódzkie', False)
    LODZKIE_PAJECZANSKI = ('pajęczański', 'łódzkie', False)
    LODZKIE_PIOTRKOWSKI = ('piotrkowski', 'łódzkie', False)
    LODZKIE_PODDEBICKI = ('poddębicki', 'łódzkie', False)
    LODZKIE_RADOMSZCZANSKI = ('radomszczański', 'łódzkie', False)
    LODZKIE_RAWSKI = ('rawski', 'łódzkie', False)
    LODZKIE_SIERADZKI = ('sieradzki', 'łódzkie', False)
    LODZKIE_SKIERNIEWICKI = ('skierniewicki', 'łódzkie', False)
    LODZKIE_TOMASZOWSKI = ('tomaszowski', 'łódzkie', False)
    LODZKIE_WIELUNSKI = ('wieluński', 'łódzkie', False)
    LODZKIE_WIERUSZOWSKI = ('wieruszowski', 'łódzkie', False)
    LODZKIE_ZDUNSKOWOLSKI = ('zduńskowolski', 'łódzkie', False)
    LODZKIE_ZGIERSKI = ('zgierski', 'łódzkie', False)
    LODZKIE_MIASTO_LODZ = ('Łódź', 'łódzkie', True)
    LODZKIE_MIASTO_PIOTRKOW_TRYBUNALSKI = ('Piotrków Trybunalski', 'łódzkie', True)
    LODZKIE_MIASTO_SKIERNIEWICE = ('Skierniewice', 'łódzkie', True)

    # Małopolskie
    MALOPOLSKIE_BOCHENSKI = ('bocheński', 'małopolskie', False)
    MALOPOLSKIE_BRZESKI = ('brzeski', 'małopolskie', False)
    MALOPOLSKIE_CHRZANOWSKI = ('chrzanowski', 'małopolskie', False)
    MALOPOLSKIE_DABROWSKI = ('dąbrowski', 'małopolskie', False)
    MALOPOLSKIE_GORLICKI = ('gorlicki', 'małopolskie', False)
    MALOPOLSKIE_KRAKOWSKI = ('krakowski', 'małopolskie', False)
    MALOPOLSKIE_LIMANOWSKI = ('limanowski', 'małopolskie', False)
    MALOPOLSKIE_MIECHOWSKI = ('miechowski', 'małopolskie', False)
    MALOPOLSKIE_MYSLENICKI = ('myślenicki', 'małopolskie', False)
    MALOPOLSKIE_NOWOSADECKI = ('nowosądecki', 'małopolskie', False)
    MALOPOLSKIE_NOWOTARSKI = ('nowotarski', 'małopolskie', False)
    MALOPOLSKIE_OLKUSKI = ('olkuski', 'małopolskie', False)
    MALOPOLSKIE_OSWIECIMSKI = ('oświęcimski', 'małopolskie', False)
    MALOPOLSKIE_PROSZOWICKI = ('proszowicki', 'małopolskie', False)
    MALOPOLSKIE_SUSKI = ('suski', 'małopolskie', False)
    MALOPOLSKIE_TARNOWSKI = ('tarnowski', 'małopolskie', False)
    MALOPOLSKIE_TATRZANSKI = ('tatrzański', 'małopolskie', False)
    MALOPOLSKIE_WADOWICKI = ('wadowicki', 'małopolskie', False)
    MALOPOLSKIE_WIELICKI = ('wielicki', 'małopolskie', False)
    MALOPOLSKIE_MIASTO_KRAKOW = ('Kraków', 'małopolskie', True)
    MALOPOLSKIE_MIASTO_NOWY_SACZ = ('Nowy Sącz', 'małopolskie', True)
    MALOPOLSKIE_MIASTO_TARNOW = ('Tarnów', 'małopolskie', True)

    # Mazowieckie
    MAZOWIECKIE_BIALOBRZESKI = ('białobrzeski', 'mazowieckie', False)
    MAZOWIECKIE_CIECHANOWSKI = ('ciechanowski', 'mazowieckie', False)
    MAZOWIECKIE_GARWOLINSKI = ('garwoliński', 'mazowieckie', False)
    MAZOWIECKIE_GOSTYNINSKI = ('gostyniński', 'mazowieckie', False)
    MAZOWIECKIE_GRODZISKI = ('grodziski', 'mazowieckie', False)
    MAZOWIECKIE_GROJECKI = ('grójecki', 'mazowieckie', False)
    MAZOWIECKIE_KOZIENICKI = ('kozienicki', 'mazowieckie', False)
    MAZOWIECKIE_LEGIONOWSKI = ('legionowski', 'mazowieckie', False)
    MAZOWIECKIE_LIPSKI = ('lipski', 'mazowieckie', False)
    MAZOWIECKIE_LOSICKI = ('łosicki', 'mazowieckie', False)
    MAZOWIECKIE_MAKOWSKI = ('makowski', 'mazowieckie', False)
    MAZOWIECKIE_MINSKI = ('miński', 'mazowieckie', False)
    MAZOWIECKIE_MLAWSKI = ('mławski', 'mazowieckie', False)
    MAZOWIECKIE_NOWODWORSKI = ('nowodworski', 'mazowieckie', False)
    MAZOWIECKIE_OSTROLECKI = ('ostrołęcki', 'mazowieckie', False)
    MAZOWIECKIE_OSTROWSKI = ('ostrowski', 'mazowieckie', False)
    MAZOWIECKIE_OTWOCKI = ('otwocki', 'mazowieckie', False)
    MAZOWIECKIE_PIASECZYNSKI = ('piaseczyński', 'mazowieckie', False)
    MAZOWIECKIE_PLOCKI = ('płocki', 'mazowieckie', False)
    MAZOWIECKIE_PLONSKI = ('płoński', 'mazowieckie', False)
    MAZOWIECKIE_PRUSZKOWSKI = ('pruszkowski', 'mazowieckie', False)
    MAZOWIECKIE_PRZASNYSKI = ('przasnyski', 'mazowieckie', False)
    MAZOWIECKIE_PRZYSUSKI = ('przysuski', 'mazowieckie', False)
    MAZOWIECKIE_PULTUSKI = ('pułtuski', 'mazowieckie', False)
    MAZOWIECKIE_RADOMSKI = ('radomski', 'mazowieckie', False)
    MAZOWIECKIE_SIEDLECKI = ('siedlecki', 'mazowieckie', False)
    MAZOWIECKIE_SIERPECKI = ('sierpecki', 'mazowieckie', False)
    MAZOWIECKIE_SOCHACZEWSKI = ('sochaczewski', 'mazowieckie', False)
    MAZOWIECKIE_SOKOLOWSKI = ('sokołowski', 'mazowieckie', False)
    MAZOWIECKIE_SZYDLOWIECKI = ('szydłowiecki', 'mazowieckie', False)
    MAZOWIECKIE_WARSZAWSKI_ZACHODNI = ('warszawski zachodni', 'mazowieckie', False)
    MAZOWIECKIE_WEGROWSKI = ('węgrowski', 'mazowieckie', False)
    MAZOWIECKIE_WOLOMINSKI = ('wołomiński', 'mazowieckie', False)
    MAZOWIECKIE_WYSZKOWSKI = ('wyszkowski', 'mazowieckie', False)
    MAZOWIECKIE_ZWOLENSKI = ('zwoleński', 'mazowieckie', False)
    MAZOWIECKIE_ZUROMINSKI = ('żuromiński', 'mazowieckie', False)
    MAZOWIECKIE_ZYRARDOWSKI = ('żyrardowski', 'mazowieckie', False)
    MAZOWIECKIE_MIASTO_OSTROLEKA = ('Ostrołęka', 'mazowieckie', True)
    MAZOWIECKIE_MIASTO_PLOCK = ('Płock', 'mazowieckie', True)
    MAZOWIECKIE_MIASTO_RADOM = ('Radom', 'mazowieckie', True)
    MAZOWIECKIE_MIASTO_SIEDLCE = ('Siedlce', 'mazowieckie', True)
    MAZOWIECKIE_MIASTO_WARSZAWA = ('Warszawa', 'mazowieckie', True)

    # Opolskie
    OPOLSKIE_BRZESKI = ('brzeski', 'opolskie', False)
    OPOLSKIE_GLUBCZYCKI = ('głubczycki', 'opolskie', False)
    OPOLSKIE_KEDZIERZYNSKO_KOZIELSKI = ('kędzierzyńsko-kozielski', 'opolskie', False)
    OPOLSKIE_KLUCZBORSKI = ('kluczborski', 'opolskie', False)
    OPOLSKIE_KRAPKOWICKI = ('krapkowicki', 'opolskie', False)
    OPOLSKIE_NAMYSLOWSKI = ('namysłowski', 'opolskie', False)
    OPOLSKIE_NYSKI = ('nyski', 'opolskie', False)
    OPOLSKIE_OLESKI = ('oleski', 'opolskie', False)
    OPOLSKIE_OPOLSKI = ('opolski', 'opolskie', False)
    OPOLSKIE_PRUDNICKI = ('prudnicki', 'opolskie', False)
    OPOLSKIE_STRZELECKI = ('strzelecki', 'opolskie', False)
    OPOLSKIE_MIASTO_OPOLE = ('Opole', 'opolskie', True)

    # Podkarpackie
    PODKARPACKIE_BIESZCZADZKI = ('bieszczadzki', 'podkarpackie', False)
    PODKARPACKIE_BRZOZOWSKI = ('brzozowski', 'podkarpackie', False)
    PODKARPACKIE_DEBICKI = ('dębicki', 'podkarpackie', False)
    PODKARPACKIE_JAROSLAWSKI = ('jarosławski', 'podkarpackie', False)
    PODKARPACKIE_JASIELSKI = ('jasielski', 'podkarpackie', False)
    PODKARPACKIE_KOLBUSZOWSKI = ('kolbuszowski', 'podkarpackie', False)
    PODKARPACKIE_KROSNIENSKI = ('krośnieński', 'podkarpackie', False)
    PODKARPACKIE_LESKI = ('leski', 'podkarpackie', False)
    PODKARPACKIE_LEZAJSKI = ('leżajski', 'podkarpackie', False)
    PODKARPACKIE_LUBACZOWSKI = ('lubaczowski', 'podkarpackie', False)
    PODKARPACKIE_LANCUCKI = ('łańcucki', 'podkarpackie', False)
    PODKARPACKIE_MIELECKI = ('mielecki', 'podkarpackie', False)
    PODKARPACKIE_NIZANSKI = ('niżański', 'podkarpackie', False)
    PODKARPACKIE_PRZEMYSKI = ('przemyski', 'podkarpackie', False)
    PODKARPACKIE_PRZEWORSKI = ('przeworski', 'podkarpackie', False)
    PODKARPACKIE_ROPCZYCKO_SEDZISZOWSKI = ('ropczycko-sędziszowski', 'podkarpackie', False)
    PODKARPACKIE_RZESZOWSKI = ('rzeszowski', 'podkarpackie', False)
    PODKARPACKIE_SANOCKI = ('sanocki', 'podkarpackie', False)
    PODKARPACKIE_STALOWOWOLSKI = ('stalowowolski', 'podkarpackie', False)
    PODKARPACKIE_STRZYZOWSKI = ('strzyżowski', 'podkarpackie', False)
    PODKARPACKIE_TARNOBRZESKI = ('tarnobrzeski', 'podkarpackie', False)
    PODKARPACKIE_MIASTO_KROSNO = ('Krosno', 'podkarpackie', True)
    PODKARPACKIE_MIASTO_PRZEMYSL = ('Przemyśl', 'podkarpackie', True)
    PODKARPACKIE_MIASTO_RZESZOW = ('Rzeszów', 'podkarpackie', True)
    PODKARPACKIE_MIASTO_TARNOBRZEG = ('Tarnobrzeg', 'podkarpackie', True)

    # Podlaskie
    PODLASKIE_AUGUSTOWSKI = ('augustowski', 'podlaskie', False)
    PODLASKIE_BIALOSTOCKI = ('białostocki', 'podlaskie', False)
    PODLASKIE_BIELSKI = ('bielski', 'podlaskie', False)
    PODLASKIE_GRAJEWSKI = ('grajewski', 'podlaskie', False)
    PODLASKIE_HAJNOWSKI = ('hajnowski', 'podlaskie', False)
    PODLASKIE_KOLNENSKI = ('kolneński', 'podlaskie', False)
    PODLASKIE_LOMZYNSKI = ('łomżyński', 'podlaskie', False)
    PODLASKIE_MONIECKI = ('moniecki', 'podlaskie', False)
    PODLASKIE_SEJNENSKI = ('sejneński', 'podlaskie', False)
    PODLASKIE_SIEMIATYCKI = ('siemiatycki', 'podlaskie', False)
    PODLASKIE_SOKOLSKI = ('sokólski', 'podlaskie', False)
    PODLASKIE_SUWALSKI = ('suwalski', 'podlaskie', False)
    PODLASKIE_WYSOKOMAZOWIECKI = ('wysokomazowiecki', 'podlaskie', False)
    PODLASKIE_ZAMBROWSKI = ('zambrowski', 'podlaskie', False)
    PODLASKIE_MIASTO_BIALYSTOK = ('Białystok', 'podlaskie', True)
    PODLASKIE_MIASTO_LOMZA = ('Łomża', 'podlaskie', True)
    PODLASKIE_MIASTO_SUWALKI = ('Suwałki', 'podlaskie', True)

    # Pomorskie
    POMORSKIE_BYTOWSKI = ('bytowski', 'pomorskie', False)
    POMORSKIE_CHOJNICKI = ('chojnicki', 'pomorskie', False)
    POMORSKIE_CZLUCHOWSKI = ('człuchowski', 'pomorskie', False)
    POMORSKIE_GDANSKI = ('gdański', 'pomorskie', False)
    POMORSKIE_KARTUSKI = ('kartuski', 'pomorskie', False)
    POMORSKIE_KOSCIERSKI = ('kościerski', 'pomorskie', False)
    POMORSKIE_KWIDZYNSKI = ('kwidzyński', 'pomorskie', False)
    POMORSKIE_LEBORSKI = ('lęborski', 'pomorskie', False)
    POMORSKIE_MALBORSKI = ('malborski', 'pomorskie', False)
    POMORSKIE_NOWODWORSKI = ('nowodworski', 'pomorskie', False)
    POMORSKIE_PUCKI = ('pucki', 'pomorskie', False)
    POMORSKIE_SLUPSKI = ('słupski', 'pomorskie', False)
    POMORSKIE_STAROGARDZKI = ('starogardzki', 'pomorskie', False)
    POMORSKIE_SZTUMSKI = ('sztumski', 'pomorskie', False)
    POMORSKIE_TCZEWSKI = ('tczewski', 'pomorskie', False)
    POMORSKIE_WEJHEROWSKI = ('wejherowski', 'pomorskie', False)
    POMORSKIE_MIASTO_GDANSK = ('Gdańsk', 'pomorskie', True)
    POMORSKIE_MIASTO_GDYNIA = ('Gdynia', 'pomorskie', True)
    POMORSKIE_MIASTO_SLUPSK = ('Słupsk', 'pomorskie', True)
    POMORSKIE_MIASTO_SOPOT = ('Sopot', 'pomorskie', True)

    # Śląskie
    SLASKIE_BEDZINSKI = ('będziński', 'śląskie', False)
    SLASKIE_BIELSKI = ('bielski', 'śląskie', False)
    SLASKIE_BIERUNSKO_LEDZINSKI = ('bieruńsko-lędziński', 'śląskie', False)
    SLASKIE_CIESZYNSKI = ('cieszyński', 'śląskie', False)
    SLASKIE_CZESTOCHOWSKI = ('częstochowski', 'śląskie', False)
    SLASKIE_GLIWICKI = ('gliwicki', 'śląskie', False)
    SLASKIE_KLOBUCKI = ('kłobucki', 'śląskie', False)
    SLASKIE_LUBLINIECKI = ('lubliniecki', 'śląskie', False)
    SLASKIE_MIKOLOWSKI = ('mikołowski', 'śląskie', False)
    SLASKIE_MYSZKOWSKI = ('myszkowski', 'śląskie', False)
    SLASKIE_PSZCZYNSKI = ('pszczyński', 'śląskie', False)
    SLASKIE_RACIBORSKI = ('raciborski', 'śląskie', False)
    SLASKIE_RYBNICKI = ('rybnicki', 'śląskie', False)
    SLASKIE_TARNOGORSKI = ('tarnogórski', 'śląskie', False)
    SLASKIE_WODZISLAWSKI = ('wodzisławski', 'śląskie', False)
    SLASKIE_ZAWIERCIANSKI = ('zawierciański', 'śląskie', False)
    SLASKIE_ZYWIECKI = ('żywiecki', 'śląskie', False)
    SLASKIE_MIASTO_BIELSKO_BIALA = ('Bielsko-Biała', 'śląskie', True)
    SLASKIE_MIASTO_BYTOM = ('Bytom', 'śląskie', True)
    SLASKIE_MIASTO_CHORZOW = ('Chorzów', 'śląskie', True)
    SLASKIE_MIASTO_CZESTOCHOWA = ('Częstochowa', 'śląskie', True)
    SLASKIE_MIASTO_DABROWA_GORNICZA = ('Dąbrowa Górnicza', 'śląskie', True)
    SLASKIE_MIASTO_GLIWICE = ('Gliwice', 'śląskie', True)
    SLASKIE_MIASTO_JASTRZEBIE_ZDROJ = ('Jastrzębie-Zdrój', 'śląskie', True)
    SLASKIE_MIASTO_JAWORZNO = ('Jaworzno', 'śląskie', True)
    SLASKIE_MIASTO_KATOWICE = ('Katowice', 'śląskie', True)
    SLASKIE_MIASTO_MYSLOWICE = ('Mysłowice', 'śląskie', True)
    SLASKIE_MIASTO_PIEKARY_SLASKIE = ('Piekary Śląskie', 'śląskie', True)
    SLASKIE_MIASTO_RUDA_SLASKA = ('Ruda Śląska', 'śląskie', True)
    SLASKIE_MIASTO_RYBNIK = ('Rybnik', 'śląskie', True)
    SLASKIE_MIASTO_SIEMIANOWICE_SLASKIE = ('Siemianowice Śląskie', 'śląskie', True)
    SLASKIE_MIASTO_SOSNOWIEC = ('Sosnowiec', 'śląskie', True)
    SLASKIE_MIASTO_SWIETOCHLOWICE = ('Świętochłowice', 'śląskie', True)
    SLASKIE_MIASTO_TYCHY = ('Tychy', 'śląskie', True)
    SLASKIE_MIASTO_ZABRZE = ('Zabrze', 'śląskie', True)
    SLASKIE_MIASTO_ZORY = ('Żory', 'śląskie', True)

    # Świętokrzyskie
    SWIETOKRZYSKIE_BUSKI = ('buski', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_JEDRZEJOWSKI = ('jędrzejowski', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_KAZIMIERSKI = ('kazimierski', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_KIELECKI = ('kielecki', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_KONECKI = ('konecki', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_OPATOWSKI = ('opatowski', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_OSTROWIECKI = ('ostrowiecki', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_PINCZOWSKI = ('pińczowski', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_SANDOMIERSKI = ('sandomierski', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_SKARZYSKI = ('skarżyski', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_STARACHOWICKI = ('starachowicki', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_STASZOWSKI = ('staszowski', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_WLOSZCZOWSKI = ('włoszczowski', 'świętokrzyskie', False)
    SWIETOKRZYSKIE_MIASTO_KIELCE = ('Kielce', 'świętokrzyskie', True)

    # Warmińsko-mazurskie
    WARMINSKO_MAZURSKIE_BARTOSZYCKI = ('bartoszycki', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_BRANIEWSKI = ('braniewski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_DZIALDOWSKI = ('działdowski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_ELBLASKI = ('elbląski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_ELCKI = ('ełcki', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_GIZYCKI = ('giżycki', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_GOLDAPSKI = ('gołdapski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_ILAWSKI = ('iławski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_KETRZYNSKI = ('kętrzyński', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_LIDZBARSKI = ('lidzbarski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_MRAGOWSKI = ('mrągowski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_NIDZICKI = ('nidzicki', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_NOWOMIEJSKI = ('nowomiejski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_OLECKI = ('olecki', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_OLSZTYNSKI = ('olsztyński', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_OSTRODZKI = ('ostródzki', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_PISKI = ('piski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_SZCZYCIENSKI = ('szczycieński', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_WEGORZEWSKI = ('węgorzewski', 'warmińsko-mazurskie', False)
    WARMINSKO_MAZURSKIE_MIASTO_ELBLAG = ('Elbląg', 'warmińsko-mazurskie', True)
    WARMINSKO_MAZURSKIE_MIASTO_OLSZTYN = ('Olsztyn', 'warmińsko-mazurskie', True)

    # Wielkopolskie
    WIELKOPOLSKIE_CHODZIESKI = ('chodzieski', 'wielkopolskie', False)
    WIELKOPOLSKIE_CZARNKOWSKO_TRZCIANECKI = ('czarnkowsko-trzcianecki', 'wielkopolskie', False)
    WIELKOPOLSKIE_GNIEZNIENSKI = ('gnieźnieński', 'wielkopolskie', False)
    WIELKOPOLSKIE_GOSTYNSKI = ('gostyński', 'wielkopolskie', False)
    WIELKOPOLSKIE_GRODZISKI = ('grodziski', 'wielkopolskie', False)
    WIELKOPOLSKIE_JAROCINSKI = ('jarociński', 'wielkopolskie', False)
    WIELKOPOLSKIE_KALISKI = ('kaliski', 'wielkopolskie', False)
    WIELKOPOLSKIE_KEPINSKI = ('kępiński', 'wielkopolskie', False)
    WIELKOPOLSKIE_KOLSKI = ('kolski', 'wielkopolskie', False)
    WIELKOPOLSKIE_KONINSKI = ('koniński', 'wielkopolskie', False)
    WIELKOPOLSKIE_KOSCIANSKI = ('kościański', 'wielkopolskie', False)
    WIELKOPOLSKIE_KROTOSZYNSKI = ('krotoszyński', 'wielkopolskie', False)
    WIELKOPOLSKIE_LESZCZYNSKI = ('leszczyński', 'wielkopolskie', False)
    WIELKOPOLSKIE_MIEDZYCHODZKI = ('międzychodzki', 'wielkopolskie', False)
    WIELKOPOLSKIE_NOWOTOMYSKI = ('nowotomyski', 'wielkopolskie', False)
    WIELKOPOLSKIE_OBORNICKI = ('obornicki', 'wielkopolskie', False)
    WIELKOPOLSKIE_OSTROWSKI = ('ostrowski', 'wielkopolskie', False)
    WIELKOPOLSKIE_OSTRZESZOWSKI = ('ostrzeszowski', 'wielkopolskie', False)
    WIELKOPOLSKIE_PILSKI = ('pilski', 'wielkopolskie', False)
    WIELKOPOLSKIE_PLESZEWSKI = ('pleszewski', 'wielkopolskie', False)
    WIELKOPOLSKIE_POZNANSKI = ('poznański', 'wielkopolskie', False)
    WIELKOPOLSKIE_RAWICKI = ('rawicki', 'wielkopolskie', False)
    WIELKOPOLSKIE_SLUPECKI = ('słupecki', 'wielkopolskie', False)
    WIELKOPOLSKIE_SZAMOTULSKI = ('szamotulski', 'wielkopolskie', False)
    WIELKOPOLSKIE_SREDZKI = ('średzki', 'wielkopolskie', False)
    WIELKOPOLSKIE_SREMSKI = ('śremski', 'wielkopolskie', False)
    WIELKOPOLSKIE_TURECKI = ('turecki', 'wielkopolskie', False)
    WIELKOPOLSKIE_WAGROWIECKI = ('wągrowiecki', 'wielkopolskie', False)
    WIELKOPOLSKIE_WOLSZTYNSKI = ('wolsztyński', 'wielkopolskie', False)
    WIELKOPOLSKIE_WRZESINSKI = ('wrzesiński', 'wielkopolskie', False)
    WIELKOPOLSKIE_ZLOTOWSKI = ('złotowski', 'wielkopolskie', False)
    WIELKOPOLSKIE_MIASTO_KALISZ = ('Kalisz', 'wielkopolskie', True)
    WIELKOPOLSKIE_MIASTO_KONIN = ('Konin', 'wielkopolskie', True)
    WIELKOPOLSKIE_MIASTO_LESZNO = ('Leszno', 'wielkopolskie', True)
    WIELKOPOLSKIE_MIASTO_POZNAN = ('Poznań', 'wielkopolskie', True)

    # Zachodniopomorskie
    ZACHODNIOPOMORSKIE_BIALOGARDZKI = ('białogardzki', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_CHOSZCZENSKI = ('choszczeński', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_DRAWSKI = ('drawski', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_GOLENIOWSKI = ('goleniowski', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_GRYFICKI = ('gryficki', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_GRYFINSKI = ('gryfiński', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_KAMIENSKI = ('kamieński', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_KOLOBRZESKI = ('kołobrzeski', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_KOSZALINSKI = ('koszaliński', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_LOBESKI = ('łobeski', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_MYSLIBORSKI = ('myśliborski', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_POLICKI = ('policki', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_PYRZYCKI = ('pyrzycki', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_SLAWIENSKI = ('sławieński', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_STARGARDZKI = ('stargardzki', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_SZCZECINECKI = ('szczecinecki', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_SWIDWINSKI = ('świdwiński', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_WALECKI = ('wałecki', 'zachodniopomorskie', False)
    ZACHODNIOPOMORSKIE_MIASTO_KOSZALIN = ('Koszalin', 'zachodniopomorskie', True)
    ZACHODNIOPOMORSKIE_MIASTO_SZCZECIN = ('Szczecin', 'zachodniopomorskie', True)
    ZACHODNIOPOMORSKIE_MIASTO_SWINOUJSCIE = ('Świnoujście', 'zachodniopomorskie', True)


"""Enum wszystkich gmin w Polsce według rejestru TERYT (TERC).

Stan danych: 1 stycznia 2026 r.
Liczba jednostek: 2 479 gmin (302 miejskie, 1 453 wiejskie,
724 miejsko-wiejskie). Miasta i obszary wiejskie będące częściami
gmin miejsko-wiejskich nie są dodawane jako oddzielne gminy.

Wartością każdego elementu Gmina jest siedmiocyfrowy identyfikator TERYT:
WWPPGGR, gdzie WW = województwo, PP = powiat, GG = gmina,
a R = rodzaj jednostki.
"""


class GminaType(str, Enum):
    MIEJSKA = "gmina miejska"
    WIEJSKA = "gmina wiejska"
    MIEJSKO_WIEJSKA = "gmina miejsko-wiejska"


class Gmina(Enum):
    """Gmina wraz z kodem TERYT i przynależnością administracyjną."""

    # Dolnośląskie
    DOLNOSLASKIE_BOLESLAWIECKI_BOLESLAWIEC_MIEJSKA = ('0201011', 'Bolesławiec', GminaType.MIEJSKA, 'dolnośląskie',
                                                      'bolesławiecki', 'powiat')
    DOLNOSLASKIE_BOLESLAWIECKI_BOLESLAWIEC_WIEJSKA = ('0201022', 'Bolesławiec', GminaType.WIEJSKA, 'dolnośląskie',
                                                      'bolesławiecki', 'powiat')
    DOLNOSLASKIE_BOLESLAWIECKI_GROMADKA_WIEJSKA = ('0201032', 'Gromadka', GminaType.WIEJSKA, 'dolnośląskie',
                                                   'bolesławiecki', 'powiat')
    DOLNOSLASKIE_BOLESLAWIECKI_NOWOGRODZIEC_MIEJSKO_WIEJSKA = ('0201043', 'Nowogrodziec', GminaType.MIEJSKO_WIEJSKA,
                                                               'dolnośląskie', 'bolesławiecki', 'powiat')
    DOLNOSLASKIE_BOLESLAWIECKI_OSIECZNICA_WIEJSKA = ('0201052', 'Osiecznica', GminaType.WIEJSKA, 'dolnośląskie',
                                                     'bolesławiecki', 'powiat')
    DOLNOSLASKIE_BOLESLAWIECKI_WARTA_BOLESLAWIECKA_WIEJSKA = ('0201062', 'Warta Bolesławiecka', GminaType.WIEJSKA,
                                                              'dolnośląskie', 'bolesławiecki', 'powiat')
    DOLNOSLASKIE_DZIERZONIOWSKI_BIELAWA_MIEJSKA = ('0202011', 'Bielawa', GminaType.MIEJSKA, 'dolnośląskie',
                                                   'dzierżoniowski', 'powiat')
    DOLNOSLASKIE_DZIERZONIOWSKI_DZIERZONIOW_MIEJSKA = ('0202021', 'Dzierżoniów', GminaType.MIEJSKA, 'dolnośląskie',
                                                       'dzierżoniowski', 'powiat')
    DOLNOSLASKIE_DZIERZONIOWSKI_PIESZYCE_MIEJSKO_WIEJSKA = ('0202033', 'Pieszyce', GminaType.MIEJSKO_WIEJSKA,
                                                            'dolnośląskie', 'dzierżoniowski', 'powiat')
    DOLNOSLASKIE_DZIERZONIOWSKI_PILAWA_GORNA_MIEJSKA = ('0202041', 'Piława Górna', GminaType.MIEJSKA, 'dolnośląskie',
                                                        'dzierżoniowski', 'powiat')
    DOLNOSLASKIE_DZIERZONIOWSKI_DZIERZONIOW_WIEJSKA = ('0202052', 'Dzierżoniów', GminaType.WIEJSKA, 'dolnośląskie',
                                                       'dzierżoniowski', 'powiat')
    DOLNOSLASKIE_DZIERZONIOWSKI_LAGIEWNIKI_WIEJSKA = ('0202062', 'Łagiewniki', GminaType.WIEJSKA, 'dolnośląskie',
                                                      'dzierżoniowski', 'powiat')
    DOLNOSLASKIE_DZIERZONIOWSKI_NIEMCZA_MIEJSKO_WIEJSKA = ('0202073', 'Niemcza', GminaType.MIEJSKO_WIEJSKA,
                                                           'dolnośląskie', 'dzierżoniowski', 'powiat')
    DOLNOSLASKIE_GLOGOWSKI_GLOGOW_MIEJSKA = ('0203011', 'Głogów', GminaType.MIEJSKA, 'dolnośląskie', 'głogowski',
                                             'powiat')
    DOLNOSLASKIE_GLOGOWSKI_GLOGOW_WIEJSKA = ('0203022', 'Głogów', GminaType.WIEJSKA, 'dolnośląskie', 'głogowski',
                                             'powiat')
    DOLNOSLASKIE_GLOGOWSKI_JERZMANOWA_WIEJSKA = ('0203032', 'Jerzmanowa', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'głogowski', 'powiat')
    DOLNOSLASKIE_GLOGOWSKI_KOTLA_WIEJSKA = ('0203042', 'Kotla', GminaType.WIEJSKA, 'dolnośląskie', 'głogowski',
                                            'powiat')
    DOLNOSLASKIE_GLOGOWSKI_PECLAW_WIEJSKA = ('0203052', 'Pęcław', GminaType.WIEJSKA, 'dolnośląskie', 'głogowski',
                                             'powiat')
    DOLNOSLASKIE_GLOGOWSKI_ZUKOWICE_WIEJSKA = ('0203062', 'Żukowice', GminaType.WIEJSKA, 'dolnośląskie', 'głogowski',
                                               'powiat')
    DOLNOSLASKIE_GOROWSKI_GORA_MIEJSKO_WIEJSKA = ('0204013', 'Góra', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                  'górowski', 'powiat')
    DOLNOSLASKIE_GOROWSKI_JEMIELNO_WIEJSKA = ('0204022', 'Jemielno', GminaType.WIEJSKA, 'dolnośląskie', 'górowski',
                                              'powiat')
    DOLNOSLASKIE_GOROWSKI_NIECHLOW_WIEJSKA = ('0204032', 'Niechlów', GminaType.WIEJSKA, 'dolnośląskie', 'górowski',
                                              'powiat')
    DOLNOSLASKIE_GOROWSKI_WASOSZ_MIEJSKO_WIEJSKA = ('0204043', 'Wąsosz', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                    'górowski', 'powiat')
    DOLNOSLASKIE_JAWORSKI_JAWOR_MIEJSKA = ('0205011', 'Jawor', GminaType.MIEJSKA, 'dolnośląskie', 'jaworski', 'powiat')
    DOLNOSLASKIE_JAWORSKI_BOLKOW_MIEJSKO_WIEJSKA = ('0205023', 'Bolków', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                    'jaworski', 'powiat')
    DOLNOSLASKIE_JAWORSKI_MECINKA_WIEJSKA = ('0205032', 'Męcinka', GminaType.WIEJSKA, 'dolnośląskie', 'jaworski',
                                             'powiat')
    DOLNOSLASKIE_JAWORSKI_MSCIWOJOW_WIEJSKA = ('0205042', 'Mściwojów', GminaType.WIEJSKA, 'dolnośląskie', 'jaworski',
                                               'powiat')
    DOLNOSLASKIE_JAWORSKI_PASZOWICE_WIEJSKA = ('0205052', 'Paszowice', GminaType.WIEJSKA, 'dolnośląskie', 'jaworski',
                                               'powiat')
    DOLNOSLASKIE_JAWORSKI_WADROZE_WIELKIE_WIEJSKA = ('0205062', 'Wądroże Wielkie', GminaType.WIEJSKA, 'dolnośląskie',
                                                     'jaworski', 'powiat')
    DOLNOSLASKIE_KARKONOSKI_KARPACZ_MIEJSKA = ('0206011', 'Karpacz', GminaType.MIEJSKA, 'dolnośląskie', 'karkonoski',
                                               'powiat')
    DOLNOSLASKIE_KARKONOSKI_KOWARY_MIEJSKA = ('0206021', 'Kowary', GminaType.MIEJSKA, 'dolnośląskie', 'karkonoski',
                                              'powiat')
    DOLNOSLASKIE_KARKONOSKI_PIECHOWICE_MIEJSKA = ('0206031', 'Piechowice', GminaType.MIEJSKA, 'dolnośląskie',
                                                  'karkonoski', 'powiat')
    DOLNOSLASKIE_KARKONOSKI_SZKLARSKA_POREBA_MIEJSKA = ('0206041', 'Szklarska Poręba', GminaType.MIEJSKA,
                                                        'dolnośląskie', 'karkonoski', 'powiat')
    DOLNOSLASKIE_KARKONOSKI_JANOWICE_WIELKIE_WIEJSKA = ('0206052', 'Janowice Wielkie', GminaType.WIEJSKA,
                                                        'dolnośląskie', 'karkonoski', 'powiat')
    DOLNOSLASKIE_KARKONOSKI_JEZOW_SUDECKI_WIEJSKA = ('0206062', 'Jeżów Sudecki', GminaType.WIEJSKA, 'dolnośląskie',
                                                     'karkonoski', 'powiat')
    DOLNOSLASKIE_KARKONOSKI_MYSLAKOWICE_WIEJSKA = ('0206072', 'Mysłakowice', GminaType.WIEJSKA, 'dolnośląskie',
                                                   'karkonoski', 'powiat')
    DOLNOSLASKIE_KARKONOSKI_PODGORZYN_WIEJSKA = ('0206082', 'Podgórzyn', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'karkonoski', 'powiat')
    DOLNOSLASKIE_KARKONOSKI_STARA_KAMIENICA_WIEJSKA = ('0206092', 'Stara Kamienica', GminaType.WIEJSKA, 'dolnośląskie',
                                                       'karkonoski', 'powiat')
    DOLNOSLASKIE_KAMIENNOGORSKI_KAMIENNA_GORA_MIEJSKA = ('0207011', 'Kamienna Góra', GminaType.MIEJSKA, 'dolnośląskie',
                                                         'kamiennogórski', 'powiat')
    DOLNOSLASKIE_KAMIENNOGORSKI_KAMIENNA_GORA_WIEJSKA = ('0207022', 'Kamienna Góra', GminaType.WIEJSKA, 'dolnośląskie',
                                                         'kamiennogórski', 'powiat')
    DOLNOSLASKIE_KAMIENNOGORSKI_LUBAWKA_MIEJSKO_WIEJSKA = ('0207033', 'Lubawka', GminaType.MIEJSKO_WIEJSKA,
                                                           'dolnośląskie', 'kamiennogórski', 'powiat')
    DOLNOSLASKIE_KAMIENNOGORSKI_MARCISZOW_WIEJSKA = ('0207042', 'Marciszów', GminaType.WIEJSKA, 'dolnośląskie',
                                                     'kamiennogórski', 'powiat')
    DOLNOSLASKIE_KLODZKI_DUSZNIKI_ZDROJ_MIEJSKA = ('0208011', 'Duszniki-Zdrój', GminaType.MIEJSKA, 'dolnośląskie',
                                                   'kłodzki', 'powiat')
    DOLNOSLASKIE_KLODZKI_KLODZKO_MIEJSKA = ('0208021', 'Kłodzko', GminaType.MIEJSKA, 'dolnośląskie', 'kłodzki',
                                            'powiat')
    DOLNOSLASKIE_KLODZKI_KUDOWA_ZDROJ_MIEJSKA = ('0208031', 'Kudowa-Zdrój', GminaType.MIEJSKA, 'dolnośląskie',
                                                 'kłodzki', 'powiat')
    DOLNOSLASKIE_KLODZKI_NOWA_RUDA_MIEJSKA = ('0208041', 'Nowa Ruda', GminaType.MIEJSKA, 'dolnośląskie', 'kłodzki',
                                              'powiat')
    DOLNOSLASKIE_KLODZKI_POLANICA_ZDROJ_MIEJSKA = ('0208051', 'Polanica-Zdrój', GminaType.MIEJSKA, 'dolnośląskie',
                                                   'kłodzki', 'powiat')
    DOLNOSLASKIE_KLODZKI_BYSTRZYCA_KLODZKA_MIEJSKO_WIEJSKA = ('0208063', 'Bystrzyca Kłodzka', GminaType.MIEJSKO_WIEJSKA,
                                                              'dolnośląskie', 'kłodzki', 'powiat')
    DOLNOSLASKIE_KLODZKI_KLODZKO_WIEJSKA = ('0208072', 'Kłodzko', GminaType.WIEJSKA, 'dolnośląskie', 'kłodzki',
                                            'powiat')
    DOLNOSLASKIE_KLODZKI_LADEK_ZDROJ_MIEJSKO_WIEJSKA = ('0208083', 'Lądek-Zdrój', GminaType.MIEJSKO_WIEJSKA,
                                                        'dolnośląskie', 'kłodzki', 'powiat')
    DOLNOSLASKIE_KLODZKI_LEWIN_KLODZKI_WIEJSKA = ('0208092', 'Lewin Kłodzki', GminaType.WIEJSKA, 'dolnośląskie',
                                                  'kłodzki', 'powiat')
    DOLNOSLASKIE_KLODZKI_MIEDZYLESIE_MIEJSKO_WIEJSKA = ('0208103', 'Międzylesie', GminaType.MIEJSKO_WIEJSKA,
                                                        'dolnośląskie', 'kłodzki', 'powiat')
    DOLNOSLASKIE_KLODZKI_NOWA_RUDA_WIEJSKA = ('0208112', 'Nowa Ruda', GminaType.WIEJSKA, 'dolnośląskie', 'kłodzki',
                                              'powiat')
    DOLNOSLASKIE_KLODZKI_RADKOW_MIEJSKO_WIEJSKA = ('0208123', 'Radków', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                   'kłodzki', 'powiat')
    DOLNOSLASKIE_KLODZKI_STRONIE_SLASKIE_MIEJSKO_WIEJSKA = ('0208133', 'Stronie Śląskie', GminaType.MIEJSKO_WIEJSKA,
                                                            'dolnośląskie', 'kłodzki', 'powiat')
    DOLNOSLASKIE_KLODZKI_SZCZYTNA_MIEJSKO_WIEJSKA = ('0208143', 'Szczytna', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                     'kłodzki', 'powiat')
    DOLNOSLASKIE_LEGNICKI_CHOJNOW_MIEJSKA = ('0209011', 'Chojnów', GminaType.MIEJSKA, 'dolnośląskie', 'legnicki',
                                             'powiat')
    DOLNOSLASKIE_LEGNICKI_CHOJNOW_WIEJSKA = ('0209022', 'Chojnów', GminaType.WIEJSKA, 'dolnośląskie', 'legnicki',
                                             'powiat')
    DOLNOSLASKIE_LEGNICKI_KROTOSZYCE_WIEJSKA = ('0209032', 'Krotoszyce', GminaType.WIEJSKA, 'dolnośląskie', 'legnicki',
                                                'powiat')
    DOLNOSLASKIE_LEGNICKI_KUNICE_WIEJSKA = ('0209042', 'Kunice', GminaType.WIEJSKA, 'dolnośląskie', 'legnicki',
                                            'powiat')
    DOLNOSLASKIE_LEGNICKI_LEGNICKIE_POLE_WIEJSKA = ('0209052', 'Legnickie Pole', GminaType.WIEJSKA, 'dolnośląskie',
                                                    'legnicki', 'powiat')
    DOLNOSLASKIE_LEGNICKI_MILKOWICE_WIEJSKA = ('0209062', 'Miłkowice', GminaType.WIEJSKA, 'dolnośląskie', 'legnicki',
                                               'powiat')
    DOLNOSLASKIE_LEGNICKI_PROCHOWICE_MIEJSKO_WIEJSKA = ('0209073', 'Prochowice', GminaType.MIEJSKO_WIEJSKA,
                                                        'dolnośląskie', 'legnicki', 'powiat')
    DOLNOSLASKIE_LEGNICKI_RUJA_WIEJSKA = ('0209082', 'Ruja', GminaType.WIEJSKA, 'dolnośląskie', 'legnicki', 'powiat')
    DOLNOSLASKIE_LUBANSKI_LUBAN_MIEJSKA = ('0210011', 'Lubań', GminaType.MIEJSKA, 'dolnośląskie', 'lubański', 'powiat')
    DOLNOSLASKIE_LUBANSKI_SWIERADOW_ZDROJ_MIEJSKA = ('0210021', 'Świeradów-Zdrój', GminaType.MIEJSKA, 'dolnośląskie',
                                                     'lubański', 'powiat')
    DOLNOSLASKIE_LUBANSKI_LESNA_MIEJSKO_WIEJSKA = ('0210033', 'Leśna', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                   'lubański', 'powiat')
    DOLNOSLASKIE_LUBANSKI_LUBAN_WIEJSKA = ('0210042', 'Lubań', GminaType.WIEJSKA, 'dolnośląskie', 'lubański', 'powiat')
    DOLNOSLASKIE_LUBANSKI_OLSZYNA_MIEJSKO_WIEJSKA = ('0210053', 'Olszyna', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                     'lubański', 'powiat')
    DOLNOSLASKIE_LUBANSKI_PLATEROWKA_WIEJSKA = ('0210062', 'Platerówka', GminaType.WIEJSKA, 'dolnośląskie', 'lubański',
                                                'powiat')
    DOLNOSLASKIE_LUBANSKI_SIEKIERCZYN_WIEJSKA = ('0210072', 'Siekierczyn', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'lubański', 'powiat')
    DOLNOSLASKIE_LUBINSKI_LUBIN_MIEJSKA = ('0211011', 'Lubin', GminaType.MIEJSKA, 'dolnośląskie', 'lubiński', 'powiat')
    DOLNOSLASKIE_LUBINSKI_LUBIN_WIEJSKA = ('0211022', 'Lubin', GminaType.WIEJSKA, 'dolnośląskie', 'lubiński', 'powiat')
    DOLNOSLASKIE_LUBINSKI_RUDNA_WIEJSKA = ('0211032', 'Rudna', GminaType.WIEJSKA, 'dolnośląskie', 'lubiński', 'powiat')
    DOLNOSLASKIE_LUBINSKI_SCINAWA_MIEJSKO_WIEJSKA = ('0211043', 'Ścinawa', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                     'lubiński', 'powiat')
    DOLNOSLASKIE_LWOWECKI_GRYFOW_SLASKI_MIEJSKO_WIEJSKA = ('0212013', 'Gryfów Śląski', GminaType.MIEJSKO_WIEJSKA,
                                                           'dolnośląskie', 'lwówecki', 'powiat')
    DOLNOSLASKIE_LWOWECKI_LUBOMIERZ_MIEJSKO_WIEJSKA = ('0212023', 'Lubomierz', GminaType.MIEJSKO_WIEJSKA,
                                                       'dolnośląskie', 'lwówecki', 'powiat')
    DOLNOSLASKIE_LWOWECKI_LWOWEK_SLASKI_MIEJSKO_WIEJSKA = ('0212033', 'Lwówek Śląski', GminaType.MIEJSKO_WIEJSKA,
                                                           'dolnośląskie', 'lwówecki', 'powiat')
    DOLNOSLASKIE_LWOWECKI_MIRSK_MIEJSKO_WIEJSKA = ('0212043', 'Mirsk', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                   'lwówecki', 'powiat')
    DOLNOSLASKIE_LWOWECKI_WLEN_MIEJSKO_WIEJSKA = ('0212053', 'Wleń', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                  'lwówecki', 'powiat')
    DOLNOSLASKIE_MILICKI_CIESZKOW_WIEJSKA = ('0213012', 'Cieszków', GminaType.WIEJSKA, 'dolnośląskie', 'milicki',
                                             'powiat')
    DOLNOSLASKIE_MILICKI_KROSNICE_WIEJSKA = ('0213022', 'Krośnice', GminaType.WIEJSKA, 'dolnośląskie', 'milicki',
                                             'powiat')
    DOLNOSLASKIE_MILICKI_MILICZ_MIEJSKO_WIEJSKA = ('0213033', 'Milicz', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                   'milicki', 'powiat')
    DOLNOSLASKIE_OLESNICKI_OLESNICA_MIEJSKA = ('0214011', 'Oleśnica', GminaType.MIEJSKA, 'dolnośląskie', 'oleśnicki',
                                               'powiat')
    DOLNOSLASKIE_OLESNICKI_BIERUTOW_MIEJSKO_WIEJSKA = ('0214023', 'Bierutów', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                       'oleśnicki', 'powiat')
    DOLNOSLASKIE_OLESNICKI_DOBROSZYCE_WIEJSKA = ('0214032', 'Dobroszyce', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'oleśnicki', 'powiat')
    DOLNOSLASKIE_OLESNICKI_DZIADOWA_KLODA_WIEJSKA = ('0214042', 'Dziadowa Kłoda', GminaType.WIEJSKA, 'dolnośląskie',
                                                     'oleśnicki', 'powiat')
    DOLNOSLASKIE_OLESNICKI_MIEDZYBORZ_MIEJSKO_WIEJSKA = ('0214053', 'Międzybórz', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'oleśnicki', 'powiat')
    DOLNOSLASKIE_OLESNICKI_OLESNICA_WIEJSKA = ('0214062', 'Oleśnica', GminaType.WIEJSKA, 'dolnośląskie', 'oleśnicki',
                                               'powiat')
    DOLNOSLASKIE_OLESNICKI_SYCOW_MIEJSKO_WIEJSKA = ('0214073', 'Syców', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                    'oleśnicki', 'powiat')
    DOLNOSLASKIE_OLESNICKI_TWARDOGORA_MIEJSKO_WIEJSKA = ('0214083', 'Twardogóra', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'oleśnicki', 'powiat')
    DOLNOSLASKIE_OLAWSKI_OLAWA_MIEJSKA = ('0215011', 'Oława', GminaType.MIEJSKA, 'dolnośląskie', 'oławski', 'powiat')
    DOLNOSLASKIE_OLAWSKI_DOMANIOW_WIEJSKA = ('0215022', 'Domaniów', GminaType.WIEJSKA, 'dolnośląskie', 'oławski',
                                             'powiat')
    DOLNOSLASKIE_OLAWSKI_JELCZ_LASKOWICE_MIEJSKO_WIEJSKA = ('0215033', 'Jelcz-Laskowice', GminaType.MIEJSKO_WIEJSKA,
                                                            'dolnośląskie', 'oławski', 'powiat')
    DOLNOSLASKIE_OLAWSKI_OLAWA_WIEJSKA = ('0215042', 'Oława', GminaType.WIEJSKA, 'dolnośląskie', 'oławski', 'powiat')
    DOLNOSLASKIE_POLKOWICKI_CHOCIANOW_MIEJSKO_WIEJSKA = ('0216013', 'Chocianów', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'polkowicki', 'powiat')
    DOLNOSLASKIE_POLKOWICKI_GAWORZYCE_WIEJSKA = ('0216022', 'Gaworzyce', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'polkowicki', 'powiat')
    DOLNOSLASKIE_POLKOWICKI_GREBOCICE_WIEJSKA = ('0216032', 'Grębocice', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'polkowicki', 'powiat')
    DOLNOSLASKIE_POLKOWICKI_POLKOWICE_MIEJSKO_WIEJSKA = ('0216043', 'Polkowice', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'polkowicki', 'powiat')
    DOLNOSLASKIE_POLKOWICKI_PRZEMKOW_MIEJSKO_WIEJSKA = ('0216053', 'Przemków', GminaType.MIEJSKO_WIEJSKA,
                                                        'dolnośląskie', 'polkowicki', 'powiat')
    DOLNOSLASKIE_POLKOWICKI_RADWANICE_WIEJSKA = ('0216062', 'Radwanice', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'polkowicki', 'powiat')
    DOLNOSLASKIE_STRZELINSKI_BOROW_WIEJSKA = ('0217012', 'Borów', GminaType.WIEJSKA, 'dolnośląskie', 'strzeliński',
                                              'powiat')
    DOLNOSLASKIE_STRZELINSKI_KONDRATOWICE_WIEJSKA = ('0217022', 'Kondratowice', GminaType.WIEJSKA, 'dolnośląskie',
                                                     'strzeliński', 'powiat')
    DOLNOSLASKIE_STRZELINSKI_PRZEWORNO_WIEJSKA = ('0217032', 'Przeworno', GminaType.WIEJSKA, 'dolnośląskie',
                                                  'strzeliński', 'powiat')
    DOLNOSLASKIE_STRZELINSKI_STRZELIN_MIEJSKO_WIEJSKA = ('0217043', 'Strzelin', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'strzeliński', 'powiat')
    DOLNOSLASKIE_STRZELINSKI_WIAZOW_MIEJSKO_WIEJSKA = ('0217053', 'Wiązów', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                       'strzeliński', 'powiat')
    DOLNOSLASKIE_SREDZKI_KOSTOMLOTY_WIEJSKA = ('0218012', 'Kostomłoty', GminaType.WIEJSKA, 'dolnośląskie', 'średzki',
                                               'powiat')
    DOLNOSLASKIE_SREDZKI_MALCZYCE_WIEJSKA = ('0218022', 'Malczyce', GminaType.WIEJSKA, 'dolnośląskie', 'średzki',
                                             'powiat')
    DOLNOSLASKIE_SREDZKI_MIEKINIA_MIEJSKO_WIEJSKA = ('0218033', 'Miękinia', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                     'średzki', 'powiat')
    DOLNOSLASKIE_SREDZKI_SRODA_SLASKA_MIEJSKO_WIEJSKA = ('0218043', 'Środa Śląska', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'średzki', 'powiat')
    DOLNOSLASKIE_SREDZKI_UDANIN_WIEJSKA = ('0218052', 'Udanin', GminaType.WIEJSKA, 'dolnośląskie', 'średzki', 'powiat')
    DOLNOSLASKIE_SWIDNICKI_SWIDNICA_MIEJSKA = ('0219011', 'Świdnica', GminaType.MIEJSKA, 'dolnośląskie', 'świdnicki',
                                               'powiat')
    DOLNOSLASKIE_SWIDNICKI_SWIEBODZICE_MIEJSKA = ('0219021', 'Świebodzice', GminaType.MIEJSKA, 'dolnośląskie',
                                                  'świdnicki', 'powiat')
    DOLNOSLASKIE_SWIDNICKI_DOBROMIERZ_WIEJSKA = ('0219032', 'Dobromierz', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'świdnicki', 'powiat')
    DOLNOSLASKIE_SWIDNICKI_JAWORZYNA_SLASKA_MIEJSKO_WIEJSKA = ('0219043', 'Jaworzyna Śląska', GminaType.MIEJSKO_WIEJSKA,
                                                               'dolnośląskie', 'świdnicki', 'powiat')
    DOLNOSLASKIE_SWIDNICKI_MARCINOWICE_WIEJSKA = ('0219052', 'Marcinowice', GminaType.WIEJSKA, 'dolnośląskie',
                                                  'świdnicki', 'powiat')
    DOLNOSLASKIE_SWIDNICKI_STRZEGOM_MIEJSKO_WIEJSKA = ('0219063', 'Strzegom', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                       'świdnicki', 'powiat')
    DOLNOSLASKIE_SWIDNICKI_SWIDNICA_WIEJSKA = ('0219072', 'Świdnica', GminaType.WIEJSKA, 'dolnośląskie', 'świdnicki',
                                               'powiat')
    DOLNOSLASKIE_SWIDNICKI_ZAROW_MIEJSKO_WIEJSKA = ('0219083', 'Żarów', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                    'świdnicki', 'powiat')
    DOLNOSLASKIE_TRZEBNICKI_OBORNIKI_SLASKIE_MIEJSKO_WIEJSKA = ('0220013', 'Oborniki Śląskie',
                                                                GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie', 'trzebnicki',
                                                                'powiat')
    DOLNOSLASKIE_TRZEBNICKI_PRUSICE_MIEJSKO_WIEJSKA = ('0220023', 'Prusice', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                       'trzebnicki', 'powiat')
    DOLNOSLASKIE_TRZEBNICKI_TRZEBNICA_MIEJSKO_WIEJSKA = ('0220033', 'Trzebnica', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'trzebnicki', 'powiat')
    DOLNOSLASKIE_TRZEBNICKI_WISZNIA_MALA_WIEJSKA = ('0220042', 'Wisznia Mała', GminaType.WIEJSKA, 'dolnośląskie',
                                                    'trzebnicki', 'powiat')
    DOLNOSLASKIE_TRZEBNICKI_ZAWONIA_WIEJSKA = ('0220052', 'Zawonia', GminaType.WIEJSKA, 'dolnośląskie', 'trzebnicki',
                                               'powiat')
    DOLNOSLASKIE_TRZEBNICKI_ZMIGROD_MIEJSKO_WIEJSKA = ('0220063', 'Żmigród', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                       'trzebnicki', 'powiat')
    DOLNOSLASKIE_WALBRZYSKI_BOGUSZOW_GORCE_MIEJSKA = ('0221011', 'Boguszów-Gorce', GminaType.MIEJSKA, 'dolnośląskie',
                                                      'wałbrzyski', 'powiat')
    DOLNOSLASKIE_WALBRZYSKI_JEDLINA_ZDROJ_MIEJSKA = ('0221021', 'Jedlina-Zdrój', GminaType.MIEJSKA, 'dolnośląskie',
                                                     'wałbrzyski', 'powiat')
    DOLNOSLASKIE_WALBRZYSKI_SZCZAWNO_ZDROJ_MIEJSKA = ('0221031', 'Szczawno-Zdrój', GminaType.MIEJSKA, 'dolnośląskie',
                                                      'wałbrzyski', 'powiat')
    DOLNOSLASKIE_WALBRZYSKI_CZARNY_BOR_WIEJSKA = ('0221042', 'Czarny Bór', GminaType.WIEJSKA, 'dolnośląskie',
                                                  'wałbrzyski', 'powiat')
    DOLNOSLASKIE_WALBRZYSKI_GLUSZYCA_MIEJSKO_WIEJSKA = ('0221053', 'Głuszyca', GminaType.MIEJSKO_WIEJSKA,
                                                        'dolnośląskie', 'wałbrzyski', 'powiat')
    DOLNOSLASKIE_WALBRZYSKI_MIEROSZOW_MIEJSKO_WIEJSKA = ('0221063', 'Mieroszów', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'wałbrzyski', 'powiat')
    DOLNOSLASKIE_WALBRZYSKI_STARE_BOGACZOWICE_WIEJSKA = ('0221072', 'Stare Bogaczowice', GminaType.WIEJSKA,
                                                         'dolnośląskie', 'wałbrzyski', 'powiat')
    DOLNOSLASKIE_WALBRZYSKI_WALIM_WIEJSKA = ('0221082', 'Walim', GminaType.WIEJSKA, 'dolnośląskie', 'wałbrzyski',
                                             'powiat')
    DOLNOSLASKIE_WOLOWSKI_BRZEG_DOLNY_MIEJSKO_WIEJSKA = ('0222013', 'Brzeg Dolny', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'wołowski', 'powiat')
    DOLNOSLASKIE_WOLOWSKI_WINSKO_WIEJSKA = ('0222022', 'Wińsko', GminaType.WIEJSKA, 'dolnośląskie', 'wołowski',
                                            'powiat')
    DOLNOSLASKIE_WOLOWSKI_WOLOW_MIEJSKO_WIEJSKA = ('0222033', 'Wołów', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                   'wołowski', 'powiat')
    DOLNOSLASKIE_WROCLAWSKI_CZERNICA_WIEJSKA = ('0223012', 'Czernica', GminaType.WIEJSKA, 'dolnośląskie', 'wrocławski',
                                                'powiat')
    DOLNOSLASKIE_WROCLAWSKI_DLUGOLEKA_WIEJSKA = ('0223022', 'Długołęka', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'wrocławski', 'powiat')
    DOLNOSLASKIE_WROCLAWSKI_JORDANOW_SLASKI_WIEJSKA = ('0223032', 'Jordanów Śląski', GminaType.WIEJSKA, 'dolnośląskie',
                                                       'wrocławski', 'powiat')
    DOLNOSLASKIE_WROCLAWSKI_KATY_WROCLAWSKIE_MIEJSKO_WIEJSKA = ('0223043', 'Kąty Wrocławskie',
                                                                GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie', 'wrocławski',
                                                                'powiat')
    DOLNOSLASKIE_WROCLAWSKI_KOBIERZYCE_WIEJSKA = ('0223052', 'Kobierzyce', GminaType.WIEJSKA, 'dolnośląskie',
                                                  'wrocławski', 'powiat')
    DOLNOSLASKIE_WROCLAWSKI_MIETKOW_WIEJSKA = ('0223062', 'Mietków', GminaType.WIEJSKA, 'dolnośląskie', 'wrocławski',
                                               'powiat')
    DOLNOSLASKIE_WROCLAWSKI_SOBOTKA_MIEJSKO_WIEJSKA = ('0223073', 'Sobótka', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                       'wrocławski', 'powiat')
    DOLNOSLASKIE_WROCLAWSKI_SIECHNICE_MIEJSKO_WIEJSKA = ('0223083', 'Siechnice', GminaType.MIEJSKO_WIEJSKA,
                                                         'dolnośląskie', 'wrocławski', 'powiat')
    DOLNOSLASKIE_WROCLAWSKI_ZORAWINA_WIEJSKA = ('0223092', 'Żórawina', GminaType.WIEJSKA, 'dolnośląskie', 'wrocławski',
                                                'powiat')
    DOLNOSLASKIE_ZABKOWICKI_BARDO_MIEJSKO_WIEJSKA = ('0224013', 'Bardo', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                     'ząbkowicki', 'powiat')
    DOLNOSLASKIE_ZABKOWICKI_CIEPLOWODY_WIEJSKA = ('0224022', 'Ciepłowody', GminaType.WIEJSKA, 'dolnośląskie',
                                                  'ząbkowicki', 'powiat')
    DOLNOSLASKIE_ZABKOWICKI_KAMIENIEC_ZABKOWICKI_MIEJSKO_WIEJSKA = ('0224033', 'Kamieniec Ząbkowicki',
                                                                    GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                                    'ząbkowicki', 'powiat')
    DOLNOSLASKIE_ZABKOWICKI_STOSZOWICE_WIEJSKA = ('0224042', 'Stoszowice', GminaType.WIEJSKA, 'dolnośląskie',
                                                  'ząbkowicki', 'powiat')
    DOLNOSLASKIE_ZABKOWICKI_ZABKOWICE_SLASKIE_MIEJSKO_WIEJSKA = ('0224053', 'Ząbkowice Śląskie',
                                                                 GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                                 'ząbkowicki', 'powiat')
    DOLNOSLASKIE_ZABKOWICKI_ZIEBICE_MIEJSKO_WIEJSKA = ('0224063', 'Ziębice', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                       'ząbkowicki', 'powiat')
    DOLNOSLASKIE_ZABKOWICKI_ZLOTY_STOK_MIEJSKO_WIEJSKA = ('0224073', 'Złoty Stok', GminaType.MIEJSKO_WIEJSKA,
                                                          'dolnośląskie', 'ząbkowicki', 'powiat')
    DOLNOSLASKIE_ZGORZELECKI_ZAWIDOW_MIEJSKA = ('0225011', 'Zawidów', GminaType.MIEJSKA, 'dolnośląskie', 'zgorzelecki',
                                                'powiat')
    DOLNOSLASKIE_ZGORZELECKI_ZGORZELEC_MIEJSKA = ('0225021', 'Zgorzelec', GminaType.MIEJSKA, 'dolnośląskie',
                                                  'zgorzelecki', 'powiat')
    DOLNOSLASKIE_ZGORZELECKI_BOGATYNIA_MIEJSKO_WIEJSKA = ('0225033', 'Bogatynia', GminaType.MIEJSKO_WIEJSKA,
                                                          'dolnośląskie', 'zgorzelecki', 'powiat')
    DOLNOSLASKIE_ZGORZELECKI_PIENSK_MIEJSKO_WIEJSKA = ('0225043', 'Pieńsk', GminaType.MIEJSKO_WIEJSKA, 'dolnośląskie',
                                                       'zgorzelecki', 'powiat')
    DOLNOSLASKIE_ZGORZELECKI_SULIKOW_WIEJSKA = ('0225052', 'Sulików', GminaType.WIEJSKA, 'dolnośląskie', 'zgorzelecki',
                                                'powiat')
    DOLNOSLASKIE_ZGORZELECKI_WEGLINIEC_MIEJSKO_WIEJSKA = ('0225063', 'Węgliniec', GminaType.MIEJSKO_WIEJSKA,
                                                          'dolnośląskie', 'zgorzelecki', 'powiat')
    DOLNOSLASKIE_ZGORZELECKI_ZGORZELEC_WIEJSKA = ('0225072', 'Zgorzelec', GminaType.WIEJSKA, 'dolnośląskie',
                                                  'zgorzelecki', 'powiat')
    DOLNOSLASKIE_ZLOTORYJSKI_WOJCIESZOW_MIEJSKA = ('0226011', 'Wojcieszów', GminaType.MIEJSKA, 'dolnośląskie',
                                                   'złotoryjski', 'powiat')
    DOLNOSLASKIE_ZLOTORYJSKI_ZLOTORYJA_MIEJSKA = ('0226021', 'Złotoryja', GminaType.MIEJSKA, 'dolnośląskie',
                                                  'złotoryjski', 'powiat')
    DOLNOSLASKIE_ZLOTORYJSKI_PIELGRZYMKA_WIEJSKA = ('0226032', 'Pielgrzymka', GminaType.WIEJSKA, 'dolnośląskie',
                                                    'złotoryjski', 'powiat')
    DOLNOSLASKIE_ZLOTORYJSKI_SWIERZAWA_MIEJSKO_WIEJSKA = ('0226043', 'Świerzawa', GminaType.MIEJSKO_WIEJSKA,
                                                          'dolnośląskie', 'złotoryjski', 'powiat')
    DOLNOSLASKIE_ZLOTORYJSKI_ZAGRODNO_WIEJSKA = ('0226052', 'Zagrodno', GminaType.WIEJSKA, 'dolnośląskie',
                                                 'złotoryjski', 'powiat')
    DOLNOSLASKIE_ZLOTORYJSKI_ZLOTORYJA_WIEJSKA = ('0226062', 'Złotoryja', GminaType.WIEJSKA, 'dolnośląskie',
                                                  'złotoryjski', 'powiat')
    DOLNOSLASKIE_JELENIA_GORA_JELENIA_GORA_MIEJSKA = ('0261011', 'Jelenia Góra', GminaType.MIEJSKA, 'dolnośląskie',
                                                      'Jelenia Góra', 'miasto na prawach powiatu')
    DOLNOSLASKIE_LEGNICA_LEGNICA_MIEJSKA = ('0262011', 'Legnica', GminaType.MIEJSKA, 'dolnośląskie', 'Legnica',
                                            'miasto na prawach powiatu')
    DOLNOSLASKIE_WROCLAW_WROCLAW_MIEJSKA = ('0264011', 'Wrocław', GminaType.MIEJSKA, 'dolnośląskie', 'Wrocław',
                                            'miasto na prawach powiatu')
    DOLNOSLASKIE_WALBRZYCH_WALBRZYCH_MIEJSKA = ('0265011', 'Wałbrzych', GminaType.MIEJSKA, 'dolnośląskie', 'Wałbrzych',
                                                'miasto na prawach powiatu')

    # Kujawsko-pomorskie
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI_ALEKSANDROW_KUJAWSKI_MIEJSKA = ('0401011', 'Aleksandrów Kujawski',
                                                                      GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                                      'aleksandrowski', 'powiat')
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI_CIECHOCINEK_MIEJSKA = ('0401021', 'Ciechocinek', GminaType.MIEJSKA,
                                                             'kujawsko-pomorskie', 'aleksandrowski', 'powiat')
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI_NIESZAWA_MIEJSKA = ('0401031', 'Nieszawa', GminaType.MIEJSKA,
                                                          'kujawsko-pomorskie', 'aleksandrowski', 'powiat')
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI_ALEKSANDROW_KUJAWSKI_WIEJSKA = ('0401042', 'Aleksandrów Kujawski',
                                                                      GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                                      'aleksandrowski', 'powiat')
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI_BADKOWO_WIEJSKA = ('0401052', 'Bądkowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                         'aleksandrowski', 'powiat')
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI_KONECK_WIEJSKA = ('0401062', 'Koneck', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                        'aleksandrowski', 'powiat')
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI_RACIAZEK_WIEJSKA = ('0401072', 'Raciążek', GminaType.WIEJSKA,
                                                          'kujawsko-pomorskie', 'aleksandrowski', 'powiat')
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI_WAGANIEC_WIEJSKA = ('0401082', 'Waganiec', GminaType.WIEJSKA,
                                                          'kujawsko-pomorskie', 'aleksandrowski', 'powiat')
    KUJAWSKO_POMORSKIE_ALEKSANDROWSKI_ZAKRZEWO_WIEJSKA = ('0401092', 'Zakrzewo', GminaType.WIEJSKA,
                                                          'kujawsko-pomorskie', 'aleksandrowski', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_BRODNICA_MIEJSKA = ('0402011', 'Brodnica', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                     'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_BOBROWO_WIEJSKA = ('0402022', 'Bobrowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_BRODNICA_WIEJSKA = ('0402032', 'Brodnica', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_BRZOZIE_WIEJSKA = ('0402042', 'Brzozie', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_GORZNO_MIEJSKO_WIEJSKA = ('0402053', 'Górzno', GminaType.MIEJSKO_WIEJSKA,
                                                           'kujawsko-pomorskie', 'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_BARTNICZKA_WIEJSKA = ('0402062', 'Bartniczka', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                       'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_JABLONOWO_POMORSKIE_MIEJSKO_WIEJSKA = ('0402073', 'Jabłonowo Pomorskie',
                                                                        GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                        'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_OSIEK_WIEJSKA = ('0402082', 'Osiek', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_SWIEDZIEBNIA_WIEJSKA = ('0402092', 'Świedziebnia', GminaType.WIEJSKA,
                                                         'kujawsko-pomorskie', 'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BRODNICKI_ZBICZNO_WIEJSKA = ('0402102', 'Zbiczno', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'brodnicki', 'powiat')
    KUJAWSKO_POMORSKIE_BYDGOSKI_BIALE_BLOTA_WIEJSKA = ('0403012', 'Białe Błota', GminaType.WIEJSKA,
                                                       'kujawsko-pomorskie', 'bydgoski', 'powiat')
    KUJAWSKO_POMORSKIE_BYDGOSKI_DABROWA_CHELMINSKA_WIEJSKA = ('0403022', 'Dąbrowa Chełmińska', GminaType.WIEJSKA,
                                                              'kujawsko-pomorskie', 'bydgoski', 'powiat')
    KUJAWSKO_POMORSKIE_BYDGOSKI_DOBRCZ_WIEJSKA = ('0403032', 'Dobrcz', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'bydgoski', 'powiat')
    KUJAWSKO_POMORSKIE_BYDGOSKI_KORONOWO_MIEJSKO_WIEJSKA = ('0403043', 'Koronowo', GminaType.MIEJSKO_WIEJSKA,
                                                            'kujawsko-pomorskie', 'bydgoski', 'powiat')
    KUJAWSKO_POMORSKIE_BYDGOSKI_NOWA_WIES_WIELKA_WIEJSKA = ('0403052', 'Nowa Wieś Wielka', GminaType.WIEJSKA,
                                                            'kujawsko-pomorskie', 'bydgoski', 'powiat')
    KUJAWSKO_POMORSKIE_BYDGOSKI_OSIELSKO_WIEJSKA = ('0403062', 'Osielsko', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'bydgoski', 'powiat')
    KUJAWSKO_POMORSKIE_BYDGOSKI_SICIENKO_WIEJSKA = ('0403072', 'Sicienko', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'bydgoski', 'powiat')
    KUJAWSKO_POMORSKIE_BYDGOSKI_SOLEC_KUJAWSKI_MIEJSKO_WIEJSKA = ('0403083', 'Solec Kujawski',
                                                                  GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                  'bydgoski', 'powiat')
    KUJAWSKO_POMORSKIE_CHELMINSKI_CHELMNO_MIEJSKA = ('0404011', 'Chełmno', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                     'chełmiński', 'powiat')
    KUJAWSKO_POMORSKIE_CHELMINSKI_CHELMNO_WIEJSKA = ('0404022', 'Chełmno', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'chełmiński', 'powiat')
    KUJAWSKO_POMORSKIE_CHELMINSKI_KIJEWO_KROLEWSKIE_WIEJSKA = ('0404032', 'Kijewo Królewskie', GminaType.WIEJSKA,
                                                               'kujawsko-pomorskie', 'chełmiński', 'powiat')
    KUJAWSKO_POMORSKIE_CHELMINSKI_LISEWO_WIEJSKA = ('0404042', 'Lisewo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'chełmiński', 'powiat')
    KUJAWSKO_POMORSKIE_CHELMINSKI_PAPOWO_BISKUPIE_WIEJSKA = ('0404052', 'Papowo Biskupie', GminaType.WIEJSKA,
                                                             'kujawsko-pomorskie', 'chełmiński', 'powiat')
    KUJAWSKO_POMORSKIE_CHELMINSKI_STOLNO_WIEJSKA = ('0404062', 'Stolno', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'chełmiński', 'powiat')
    KUJAWSKO_POMORSKIE_CHELMINSKI_UNISLAW_WIEJSKA = ('0404072', 'Unisław', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'chełmiński', 'powiat')
    KUJAWSKO_POMORSKIE_GOLUBSKO_DOBRZYNSKI_GOLUB_DOBRZYN_MIEJSKA = ('0405011', 'Golub-Dobrzyń', GminaType.MIEJSKA,
                                                                    'kujawsko-pomorskie', 'golubsko-dobrzyński',
                                                                    'powiat')
    KUJAWSKO_POMORSKIE_GOLUBSKO_DOBRZYNSKI_CIECHOCIN_WIEJSKA = ('0405022', 'Ciechocin', GminaType.WIEJSKA,
                                                                'kujawsko-pomorskie', 'golubsko-dobrzyński', 'powiat')
    KUJAWSKO_POMORSKIE_GOLUBSKO_DOBRZYNSKI_GOLUB_DOBRZYN_WIEJSKA = ('0405032', 'Golub-Dobrzyń', GminaType.WIEJSKA,
                                                                    'kujawsko-pomorskie', 'golubsko-dobrzyński',
                                                                    'powiat')
    KUJAWSKO_POMORSKIE_GOLUBSKO_DOBRZYNSKI_KOWALEWO_POMORSKIE_MIEJSKO_WIEJSKA = ('0405043', 'Kowalewo Pomorskie',
                                                                                 GminaType.MIEJSKO_WIEJSKA,
                                                                                 'kujawsko-pomorskie',
                                                                                 'golubsko-dobrzyński', 'powiat')
    KUJAWSKO_POMORSKIE_GOLUBSKO_DOBRZYNSKI_RADOMIN_WIEJSKA = ('0405052', 'Radomin', GminaType.WIEJSKA,
                                                              'kujawsko-pomorskie', 'golubsko-dobrzyński', 'powiat')
    KUJAWSKO_POMORSKIE_GOLUBSKO_DOBRZYNSKI_ZBOJNO_WIEJSKA = ('0405062', 'Zbójno', GminaType.WIEJSKA,
                                                             'kujawsko-pomorskie', 'golubsko-dobrzyński', 'powiat')
    KUJAWSKO_POMORSKIE_GRUDZIADZKI_GRUDZIADZ_WIEJSKA = ('0406012', 'Grudziądz', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                        'grudziądzki', 'powiat')
    KUJAWSKO_POMORSKIE_GRUDZIADZKI_GRUTA_WIEJSKA = ('0406022', 'Gruta', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'grudziądzki', 'powiat')
    KUJAWSKO_POMORSKIE_GRUDZIADZKI_LASIN_MIEJSKO_WIEJSKA = ('0406033', 'Łasin', GminaType.MIEJSKO_WIEJSKA,
                                                            'kujawsko-pomorskie', 'grudziądzki', 'powiat')
    KUJAWSKO_POMORSKIE_GRUDZIADZKI_RADZYN_CHELMINSKI_MIEJSKO_WIEJSKA = ('0406043', 'Radzyń Chełmiński',
                                                                        GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                        'grudziądzki', 'powiat')
    KUJAWSKO_POMORSKIE_GRUDZIADZKI_ROGOZNO_WIEJSKA = ('0406052', 'Rogóźno', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                      'grudziądzki', 'powiat')
    KUJAWSKO_POMORSKIE_GRUDZIADZKI_SWIECIE_NAD_OSA_WIEJSKA = ('0406062', 'Świecie nad Osą', GminaType.WIEJSKA,
                                                              'kujawsko-pomorskie', 'grudziądzki', 'powiat')
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI_INOWROCLAW_MIEJSKA = ('0407011', 'Inowrocław', GminaType.MIEJSKA,
                                                           'kujawsko-pomorskie', 'inowrocławski', 'powiat')
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI_DABROWA_BISKUPIA_WIEJSKA = ('0407022', 'Dąbrowa Biskupia', GminaType.WIEJSKA,
                                                                 'kujawsko-pomorskie', 'inowrocławski', 'powiat')
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI_GNIEWKOWO_MIEJSKO_WIEJSKA = ('0407033', 'Gniewkowo', GminaType.MIEJSKO_WIEJSKA,
                                                                  'kujawsko-pomorskie', 'inowrocławski', 'powiat')
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI_INOWROCLAW_WIEJSKA = ('0407042', 'Inowrocław', GminaType.WIEJSKA,
                                                           'kujawsko-pomorskie', 'inowrocławski', 'powiat')
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI_JANIKOWO_MIEJSKO_WIEJSKA = ('0407053', 'Janikowo', GminaType.MIEJSKO_WIEJSKA,
                                                                 'kujawsko-pomorskie', 'inowrocławski', 'powiat')
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI_KRUSZWICA_MIEJSKO_WIEJSKA = ('0407063', 'Kruszwica', GminaType.MIEJSKO_WIEJSKA,
                                                                  'kujawsko-pomorskie', 'inowrocławski', 'powiat')
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI_PAKOSC_MIEJSKO_WIEJSKA = ('0407073', 'Pakość', GminaType.MIEJSKO_WIEJSKA,
                                                               'kujawsko-pomorskie', 'inowrocławski', 'powiat')
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI_ROJEWO_WIEJSKA = ('0407082', 'Rojewo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                       'inowrocławski', 'powiat')
    KUJAWSKO_POMORSKIE_INOWROCLAWSKI_ZLOTNIKI_KUJAWSKIE_WIEJSKA = ('0407092', 'Złotniki Kujawskie', GminaType.WIEJSKA,
                                                                   'kujawsko-pomorskie', 'inowrocławski', 'powiat')
    KUJAWSKO_POMORSKIE_LIPNOWSKI_LIPNO_MIEJSKA = ('0408011', 'Lipno', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                  'lipnowski', 'powiat')
    KUJAWSKO_POMORSKIE_LIPNOWSKI_BOBROWNIKI_MIEJSKO_WIEJSKA = ('0408023', 'Bobrowniki', GminaType.MIEJSKO_WIEJSKA,
                                                               'kujawsko-pomorskie', 'lipnowski', 'powiat')
    KUJAWSKO_POMORSKIE_LIPNOWSKI_CHROSTKOWO_WIEJSKA = ('0408032', 'Chrostkowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                       'lipnowski', 'powiat')
    KUJAWSKO_POMORSKIE_LIPNOWSKI_DOBRZYN_NAD_WISLA_MIEJSKO_WIEJSKA = ('0408043', 'Dobrzyń nad Wisłą',
                                                                      GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                      'lipnowski', 'powiat')
    KUJAWSKO_POMORSKIE_LIPNOWSKI_KIKOL_MIEJSKO_WIEJSKA = ('0408053', 'Kikół', GminaType.MIEJSKO_WIEJSKA,
                                                          'kujawsko-pomorskie', 'lipnowski', 'powiat')
    KUJAWSKO_POMORSKIE_LIPNOWSKI_LIPNO_WIEJSKA = ('0408062', 'Lipno', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'lipnowski', 'powiat')
    KUJAWSKO_POMORSKIE_LIPNOWSKI_SKEPE_MIEJSKO_WIEJSKA = ('0408073', 'Skępe', GminaType.MIEJSKO_WIEJSKA,
                                                          'kujawsko-pomorskie', 'lipnowski', 'powiat')
    KUJAWSKO_POMORSKIE_LIPNOWSKI_TLUCHOWO_WIEJSKA = ('0408082', 'Tłuchowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'lipnowski', 'powiat')
    KUJAWSKO_POMORSKIE_LIPNOWSKI_WIELGIE_WIEJSKA = ('0408092', 'Wielgie', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'lipnowski', 'powiat')
    KUJAWSKO_POMORSKIE_MOGILENSKI_DABROWA_WIEJSKA = ('0409012', 'Dąbrowa', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'mogileński', 'powiat')
    KUJAWSKO_POMORSKIE_MOGILENSKI_JEZIORA_WIELKIE_WIEJSKA = ('0409022', 'Jeziora Wielkie', GminaType.WIEJSKA,
                                                             'kujawsko-pomorskie', 'mogileński', 'powiat')
    KUJAWSKO_POMORSKIE_MOGILENSKI_MOGILNO_MIEJSKO_WIEJSKA = ('0409033', 'Mogilno', GminaType.MIEJSKO_WIEJSKA,
                                                             'kujawsko-pomorskie', 'mogileński', 'powiat')
    KUJAWSKO_POMORSKIE_MOGILENSKI_STRZELNO_MIEJSKO_WIEJSKA = ('0409043', 'Strzelno', GminaType.MIEJSKO_WIEJSKA,
                                                              'kujawsko-pomorskie', 'mogileński', 'powiat')
    KUJAWSKO_POMORSKIE_NAKIELSKI_KCYNIA_MIEJSKO_WIEJSKA = ('0410013', 'Kcynia', GminaType.MIEJSKO_WIEJSKA,
                                                           'kujawsko-pomorskie', 'nakielski', 'powiat')
    KUJAWSKO_POMORSKIE_NAKIELSKI_MROCZA_MIEJSKO_WIEJSKA = ('0410023', 'Mrocza', GminaType.MIEJSKO_WIEJSKA,
                                                           'kujawsko-pomorskie', 'nakielski', 'powiat')
    KUJAWSKO_POMORSKIE_NAKIELSKI_NAKLO_NAD_NOTECIA_MIEJSKO_WIEJSKA = ('0410033', 'Nakło nad Notecią',
                                                                      GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                      'nakielski', 'powiat')
    KUJAWSKO_POMORSKIE_NAKIELSKI_SADKI_WIEJSKA = ('0410042', 'Sadki', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'nakielski', 'powiat')
    KUJAWSKO_POMORSKIE_NAKIELSKI_SZUBIN_MIEJSKO_WIEJSKA = ('0410053', 'Szubin', GminaType.MIEJSKO_WIEJSKA,
                                                           'kujawsko-pomorskie', 'nakielski', 'powiat')
    KUJAWSKO_POMORSKIE_RADZIEJOWSKI_RADZIEJOW_MIEJSKA = ('0411011', 'Radziejów', GminaType.MIEJSKA,
                                                         'kujawsko-pomorskie', 'radziejowski', 'powiat')
    KUJAWSKO_POMORSKIE_RADZIEJOWSKI_BYTON_WIEJSKA = ('0411022', 'Bytoń', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'radziejowski', 'powiat')
    KUJAWSKO_POMORSKIE_RADZIEJOWSKI_DOBRE_WIEJSKA = ('0411032', 'Dobre', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'radziejowski', 'powiat')
    KUJAWSKO_POMORSKIE_RADZIEJOWSKI_OSIECINY_WIEJSKA = ('0411042', 'Osięciny', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                        'radziejowski', 'powiat')
    KUJAWSKO_POMORSKIE_RADZIEJOWSKI_PIOTRKOW_KUJAWSKI_MIEJSKO_WIEJSKA = ('0411053', 'Piotrków Kujawski',
                                                                         GminaType.MIEJSKO_WIEJSKA,
                                                                         'kujawsko-pomorskie', 'radziejowski', 'powiat')
    KUJAWSKO_POMORSKIE_RADZIEJOWSKI_RADZIEJOW_WIEJSKA = ('0411062', 'Radziejów', GminaType.WIEJSKA,
                                                         'kujawsko-pomorskie', 'radziejowski', 'powiat')
    KUJAWSKO_POMORSKIE_RADZIEJOWSKI_TOPOLKA_WIEJSKA = ('0411072', 'Topólka', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                       'radziejowski', 'powiat')
    KUJAWSKO_POMORSKIE_RYPINSKI_RYPIN_MIEJSKA = ('0412011', 'Rypin', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                 'rypiński', 'powiat')
    KUJAWSKO_POMORSKIE_RYPINSKI_BRZUZE_WIEJSKA = ('0412022', 'Brzuze', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'rypiński', 'powiat')
    KUJAWSKO_POMORSKIE_RYPINSKI_ROGOWO_WIEJSKA = ('0412032', 'Rogowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'rypiński', 'powiat')
    KUJAWSKO_POMORSKIE_RYPINSKI_RYPIN_WIEJSKA = ('0412042', 'Rypin', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                 'rypiński', 'powiat')
    KUJAWSKO_POMORSKIE_RYPINSKI_SKRWILNO_WIEJSKA = ('0412052', 'Skrwilno', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'rypiński', 'powiat')
    KUJAWSKO_POMORSKIE_RYPINSKI_WAPIELSK_WIEJSKA = ('0412062', 'Wąpielsk', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'rypiński', 'powiat')
    KUJAWSKO_POMORSKIE_SEPOLENSKI_KAMIEN_KRAJENSKI_MIEJSKO_WIEJSKA = ('0413013', 'Kamień Krajeński',
                                                                      GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                      'sępoleński', 'powiat')
    KUJAWSKO_POMORSKIE_SEPOLENSKI_SEPOLNO_KRAJENSKIE_MIEJSKO_WIEJSKA = ('0413023', 'Sępólno Krajeńskie',
                                                                        GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                        'sępoleński', 'powiat')
    KUJAWSKO_POMORSKIE_SEPOLENSKI_SOSNO_WIEJSKA = ('0413032', 'Sośno', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                   'sępoleński', 'powiat')
    KUJAWSKO_POMORSKIE_SEPOLENSKI_WIECBORK_MIEJSKO_WIEJSKA = ('0413043', 'Więcbork', GminaType.MIEJSKO_WIEJSKA,
                                                              'kujawsko-pomorskie', 'sępoleński', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_BUKOWIEC_WIEJSKA = ('0414012', 'Bukowiec', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                   'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_DRAGACZ_WIEJSKA = ('0414022', 'Dragacz', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_DRZYCIM_WIEJSKA = ('0414032', 'Drzycim', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_JEZEWO_WIEJSKA = ('0414042', 'Jeżewo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                 'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_LNIANO_WIEJSKA = ('0414052', 'Lniano', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                 'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_NOWE_MIEJSKO_WIEJSKA = ('0414063', 'Nowe', GminaType.MIEJSKO_WIEJSKA,
                                                       'kujawsko-pomorskie', 'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_OSIE_WIEJSKA = ('0414072', 'Osie', GminaType.WIEJSKA, 'kujawsko-pomorskie', 'świecki',
                                               'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_PRUSZCZ_MIEJSKO_WIEJSKA = ('0414083', 'Pruszcz', GminaType.MIEJSKO_WIEJSKA,
                                                          'kujawsko-pomorskie', 'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_SWIECIE_MIEJSKO_WIEJSKA = ('0414093', 'Świecie', GminaType.MIEJSKO_WIEJSKA,
                                                          'kujawsko-pomorskie', 'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_SWIEKATOWO_WIEJSKA = ('0414102', 'Świekatowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_SWIECKI_WARLUBIE_WIEJSKA = ('0414112', 'Warlubie', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                   'świecki', 'powiat')
    KUJAWSKO_POMORSKIE_TORUNSKI_CHELMZA_MIEJSKA = ('0415011', 'Chełmża', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                   'toruński', 'powiat')
    KUJAWSKO_POMORSKIE_TORUNSKI_CHELMZA_WIEJSKA = ('0415022', 'Chełmża', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                   'toruński', 'powiat')
    KUJAWSKO_POMORSKIE_TORUNSKI_CZERNIKOWO_WIEJSKA = ('0415032', 'Czernikowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                      'toruński', 'powiat')
    KUJAWSKO_POMORSKIE_TORUNSKI_LUBICZ_WIEJSKA = ('0415042', 'Lubicz', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'toruński', 'powiat')
    KUJAWSKO_POMORSKIE_TORUNSKI_LUBIANKA_WIEJSKA = ('0415052', 'Łubianka', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'toruński', 'powiat')
    KUJAWSKO_POMORSKIE_TORUNSKI_LYSOMICE_WIEJSKA = ('0415062', 'Łysomice', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'toruński', 'powiat')
    KUJAWSKO_POMORSKIE_TORUNSKI_OBROWO_WIEJSKA = ('0415072', 'Obrowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'toruński', 'powiat')
    KUJAWSKO_POMORSKIE_TORUNSKI_WIELKA_NIESZAWKA_WIEJSKA = ('0415082', 'Wielka Nieszawka', GminaType.WIEJSKA,
                                                            'kujawsko-pomorskie', 'toruński', 'powiat')
    KUJAWSKO_POMORSKIE_TORUNSKI_ZLAWIES_WIELKA_WIEJSKA = ('0415092', 'Zławieś Wielka', GminaType.WIEJSKA,
                                                          'kujawsko-pomorskie', 'toruński', 'powiat')
    KUJAWSKO_POMORSKIE_TUCHOLSKI_CEKCYN_WIEJSKA = ('0416012', 'Cekcyn', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                   'tucholski', 'powiat')
    KUJAWSKO_POMORSKIE_TUCHOLSKI_GOSTYCYN_WIEJSKA = ('0416022', 'Gostycyn', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'tucholski', 'powiat')
    KUJAWSKO_POMORSKIE_TUCHOLSKI_KESOWO_WIEJSKA = ('0416032', 'Kęsowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                   'tucholski', 'powiat')
    KUJAWSKO_POMORSKIE_TUCHOLSKI_LUBIEWO_WIEJSKA = ('0416042', 'Lubiewo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'tucholski', 'powiat')
    KUJAWSKO_POMORSKIE_TUCHOLSKI_SLIWICE_WIEJSKA = ('0416052', 'Śliwice', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'tucholski', 'powiat')
    KUJAWSKO_POMORSKIE_TUCHOLSKI_TUCHOLA_MIEJSKO_WIEJSKA = ('0416063', 'Tuchola', GminaType.MIEJSKO_WIEJSKA,
                                                            'kujawsko-pomorskie', 'tucholski', 'powiat')
    KUJAWSKO_POMORSKIE_WABRZESKI_WABRZEZNO_MIEJSKA = ('0417011', 'Wąbrzeźno', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                      'wąbrzeski', 'powiat')
    KUJAWSKO_POMORSKIE_WABRZESKI_DEBOWA_LAKA_WIEJSKA = ('0417022', 'Dębowa Łąka', GminaType.WIEJSKA,
                                                        'kujawsko-pomorskie', 'wąbrzeski', 'powiat')
    KUJAWSKO_POMORSKIE_WABRZESKI_KSIAZKI_WIEJSKA = ('0417032', 'Książki', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'wąbrzeski', 'powiat')
    KUJAWSKO_POMORSKIE_WABRZESKI_PLUZNICA_WIEJSKA = ('0417042', 'Płużnica', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'wąbrzeski', 'powiat')
    KUJAWSKO_POMORSKIE_WABRZESKI_RYNSK_WIEJSKA = ('0417052', 'Ryńsk', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                  'wąbrzeski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_KOWAL_MIEJSKA = ('0418011', 'Kowal', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                   'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_BARUCHOWO_WIEJSKA = ('0418022', 'Baruchowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                       'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_BONIEWO_WIEJSKA = ('0418032', 'Boniewo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_BRZESC_KUJAWSKI_MIEJSKO_WIEJSKA = ('0418043', 'Brześć Kujawski',
                                                                     GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                     'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_CHOCEN_WIEJSKA = ('0418052', 'Choceń', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                    'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_CHODECZ_MIEJSKO_WIEJSKA = ('0418063', 'Chodecz', GminaType.MIEJSKO_WIEJSKA,
                                                             'kujawsko-pomorskie', 'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_FABIANKI_WIEJSKA = ('0418072', 'Fabianki', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                      'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_IZBICA_KUJAWSKA_MIEJSKO_WIEJSKA = ('0418083', 'Izbica Kujawska',
                                                                     GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                     'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_KOWAL_WIEJSKA = ('0418092', 'Kowal', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                   'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_LUBANIE_WIEJSKA = ('0418102', 'Lubanie', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                     'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_LUBIEN_KUJAWSKI_MIEJSKO_WIEJSKA = ('0418113', 'Lubień Kujawski',
                                                                     GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                     'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_LUBRANIEC_MIEJSKO_WIEJSKA = ('0418123', 'Lubraniec', GminaType.MIEJSKO_WIEJSKA,
                                                               'kujawsko-pomorskie', 'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_WLOCLAWSKI_WLOCLAWEK_WIEJSKA = ('0418132', 'Włocławek', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                       'włocławski', 'powiat')
    KUJAWSKO_POMORSKIE_ZNINSKI_BARCIN_MIEJSKO_WIEJSKA = ('0419013', 'Barcin', GminaType.MIEJSKO_WIEJSKA,
                                                         'kujawsko-pomorskie', 'żniński', 'powiat')
    KUJAWSKO_POMORSKIE_ZNINSKI_GASAWA_MIEJSKO_WIEJSKA = ('0419023', 'Gąsawa', GminaType.MIEJSKO_WIEJSKA,
                                                         'kujawsko-pomorskie', 'żniński', 'powiat')
    KUJAWSKO_POMORSKIE_ZNINSKI_JANOWIEC_WIELKOPOLSKI_MIEJSKO_WIEJSKA = ('0419033', 'Janowiec Wielkopolski',
                                                                        GminaType.MIEJSKO_WIEJSKA, 'kujawsko-pomorskie',
                                                                        'żniński', 'powiat')
    KUJAWSKO_POMORSKIE_ZNINSKI_LABISZYN_MIEJSKO_WIEJSKA = ('0419043', 'Łabiszyn', GminaType.MIEJSKO_WIEJSKA,
                                                           'kujawsko-pomorskie', 'żniński', 'powiat')
    KUJAWSKO_POMORSKIE_ZNINSKI_ROGOWO_WIEJSKA = ('0419052', 'Rogowo', GminaType.WIEJSKA, 'kujawsko-pomorskie',
                                                 'żniński', 'powiat')
    KUJAWSKO_POMORSKIE_ZNINSKI_ZNIN_MIEJSKO_WIEJSKA = ('0419063', 'Żnin', GminaType.MIEJSKO_WIEJSKA,
                                                       'kujawsko-pomorskie', 'żniński', 'powiat')
    KUJAWSKO_POMORSKIE_BYDGOSZCZ_BYDGOSZCZ_MIEJSKA = ('0461011', 'Bydgoszcz', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                      'Bydgoszcz', 'miasto na prawach powiatu')
    KUJAWSKO_POMORSKIE_GRUDZIADZ_GRUDZIADZ_MIEJSKA = ('0462011', 'Grudziądz', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                      'Grudziądz', 'miasto na prawach powiatu')
    KUJAWSKO_POMORSKIE_TORUN_TORUN_MIEJSKA = ('0463011', 'Toruń', GminaType.MIEJSKA, 'kujawsko-pomorskie', 'Toruń',
                                              'miasto na prawach powiatu')
    KUJAWSKO_POMORSKIE_WLOCLAWEK_WLOCLAWEK_MIEJSKA = ('0464011', 'Włocławek', GminaType.MIEJSKA, 'kujawsko-pomorskie',
                                                      'Włocławek', 'miasto na prawach powiatu')

    # Lubelskie
    LUBELSKIE_BIALSKI_MIEDZYRZEC_PODLASKI_MIEJSKA = ('0601011', 'Międzyrzec Podlaski', GminaType.MIEJSKA, 'lubelskie',
                                                     'bialski', 'powiat')
    LUBELSKIE_BIALSKI_TERESPOL_MIEJSKA = ('0601021', 'Terespol', GminaType.MIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_BIALA_PODLASKA_WIEJSKA = ('0601032', 'Biała Podlaska', GminaType.WIEJSKA, 'lubelskie', 'bialski',
                                                'powiat')
    LUBELSKIE_BIALSKI_DRELOW_WIEJSKA = ('0601042', 'Drelów', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_JANOW_PODLASKI_MIEJSKO_WIEJSKA = ('0601053', 'Janów Podlaski', GminaType.MIEJSKO_WIEJSKA,
                                                        'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_KODEN_WIEJSKA = ('0601062', 'Kodeń', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_KONSTANTYNOW_WIEJSKA = ('0601072', 'Konstantynów', GminaType.WIEJSKA, 'lubelskie', 'bialski',
                                              'powiat')
    LUBELSKIE_BIALSKI_LESNA_PODLASKA_WIEJSKA = ('0601082', 'Leśna Podlaska', GminaType.WIEJSKA, 'lubelskie', 'bialski',
                                                'powiat')
    LUBELSKIE_BIALSKI_LOMAZY_WIEJSKA = ('0601092', 'Łomazy', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_MIEDZYRZEC_PODLASKI_WIEJSKA = ('0601102', 'Międzyrzec Podlaski', GminaType.WIEJSKA, 'lubelskie',
                                                     'bialski', 'powiat')
    LUBELSKIE_BIALSKI_PISZCZAC_MIEJSKO_WIEJSKA = ('0601113', 'Piszczac', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                  'bialski', 'powiat')
    LUBELSKIE_BIALSKI_ROKITNO_WIEJSKA = ('0601122', 'Rokitno', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_ROSSOSZ_WIEJSKA = ('0601132', 'Rossosz', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_SLAWATYCZE_WIEJSKA = ('0601142', 'Sławatycze', GminaType.WIEJSKA, 'lubelskie', 'bialski',
                                            'powiat')
    LUBELSKIE_BIALSKI_SOSNOWKA_WIEJSKA = ('0601152', 'Sosnówka', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_TERESPOL_WIEJSKA = ('0601162', 'Terespol', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_TUCZNA_WIEJSKA = ('0601172', 'Tuczna', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_WISZNICE_WIEJSKA = ('0601182', 'Wisznice', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BIALSKI_ZALESIE_WIEJSKA = ('0601192', 'Zalesie', GminaType.WIEJSKA, 'lubelskie', 'bialski', 'powiat')
    LUBELSKIE_BILGORAJSKI_BILGORAJ_MIEJSKA = ('0602011', 'Biłgoraj', GminaType.MIEJSKA, 'lubelskie', 'biłgorajski',
                                              'powiat')
    LUBELSKIE_BILGORAJSKI_ALEKSANDROW_WIEJSKA = ('0602022', 'Aleksandrów', GminaType.WIEJSKA, 'lubelskie',
                                                 'biłgorajski', 'powiat')
    LUBELSKIE_BILGORAJSKI_BILGORAJ_WIEJSKA = ('0602032', 'Biłgoraj', GminaType.WIEJSKA, 'lubelskie', 'biłgorajski',
                                              'powiat')
    LUBELSKIE_BILGORAJSKI_BISZCZA_WIEJSKA = ('0602042', 'Biszcza', GminaType.WIEJSKA, 'lubelskie', 'biłgorajski',
                                             'powiat')
    LUBELSKIE_BILGORAJSKI_FRAMPOL_MIEJSKO_WIEJSKA = ('0602053', 'Frampol', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                     'biłgorajski', 'powiat')
    LUBELSKIE_BILGORAJSKI_GORAJ_MIEJSKO_WIEJSKA = ('0602063', 'Goraj', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                   'biłgorajski', 'powiat')
    LUBELSKIE_BILGORAJSKI_JOZEFOW_MIEJSKO_WIEJSKA = ('0602073', 'Józefów', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                     'biłgorajski', 'powiat')
    LUBELSKIE_BILGORAJSKI_KSIEZPOL_WIEJSKA = ('0602082', 'Księżpol', GminaType.WIEJSKA, 'lubelskie', 'biłgorajski',
                                              'powiat')
    LUBELSKIE_BILGORAJSKI_LUKOWA_WIEJSKA = ('0602092', 'Łukowa', GminaType.WIEJSKA, 'lubelskie', 'biłgorajski',
                                            'powiat')
    LUBELSKIE_BILGORAJSKI_OBSZA_WIEJSKA = ('0602102', 'Obsza', GminaType.WIEJSKA, 'lubelskie', 'biłgorajski', 'powiat')
    LUBELSKIE_BILGORAJSKI_POTOK_GORNY_WIEJSKA = ('0602112', 'Potok Górny', GminaType.WIEJSKA, 'lubelskie',
                                                 'biłgorajski', 'powiat')
    LUBELSKIE_BILGORAJSKI_TARNOGROD_MIEJSKO_WIEJSKA = ('0602123', 'Tarnogród', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                       'biłgorajski', 'powiat')
    LUBELSKIE_BILGORAJSKI_TERESZPOL_WIEJSKA = ('0602132', 'Tereszpol', GminaType.WIEJSKA, 'lubelskie', 'biłgorajski',
                                               'powiat')
    LUBELSKIE_BILGORAJSKI_TUROBIN_MIEJSKO_WIEJSKA = ('0602143', 'Turobin', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                     'biłgorajski', 'powiat')
    LUBELSKIE_CHELMSKI_REJOWIEC_FABRYCZNY_MIEJSKA = ('0603011', 'Rejowiec Fabryczny', GminaType.MIEJSKA, 'lubelskie',
                                                     'chełmski', 'powiat')
    LUBELSKIE_CHELMSKI_BIALOPOLE_WIEJSKA = ('0603022', 'Białopole', GminaType.WIEJSKA, 'lubelskie', 'chełmski',
                                            'powiat')
    LUBELSKIE_CHELMSKI_CHELM_WIEJSKA = ('0603032', 'Chełm', GminaType.WIEJSKA, 'lubelskie', 'chełmski', 'powiat')
    LUBELSKIE_CHELMSKI_DOROHUSK_WIEJSKA = ('0603042', 'Dorohusk', GminaType.WIEJSKA, 'lubelskie', 'chełmski', 'powiat')
    LUBELSKIE_CHELMSKI_DUBIENKA_WIEJSKA = ('0603052', 'Dubienka', GminaType.WIEJSKA, 'lubelskie', 'chełmski', 'powiat')
    LUBELSKIE_CHELMSKI_KAMIEN_WIEJSKA = ('0603062', 'Kamień', GminaType.WIEJSKA, 'lubelskie', 'chełmski', 'powiat')
    LUBELSKIE_CHELMSKI_LESNIOWICE_WIEJSKA = ('0603072', 'Leśniowice', GminaType.WIEJSKA, 'lubelskie', 'chełmski',
                                             'powiat')
    LUBELSKIE_CHELMSKI_REJOWIEC_FABRYCZNY_WIEJSKA = ('0603082', 'Rejowiec Fabryczny', GminaType.WIEJSKA, 'lubelskie',
                                                     'chełmski', 'powiat')
    LUBELSKIE_CHELMSKI_RUDA_HUTA_WIEJSKA = ('0603092', 'Ruda-Huta', GminaType.WIEJSKA, 'lubelskie', 'chełmski',
                                            'powiat')
    LUBELSKIE_CHELMSKI_SAWIN_WIEJSKA = ('0603102', 'Sawin', GminaType.WIEJSKA, 'lubelskie', 'chełmski', 'powiat')
    LUBELSKIE_CHELMSKI_SIEDLISZCZE_MIEJSKO_WIEJSKA = ('0603113', 'Siedliszcze', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                      'chełmski', 'powiat')
    LUBELSKIE_CHELMSKI_WIERZBICA_WIEJSKA = ('0603122', 'Wierzbica', GminaType.WIEJSKA, 'lubelskie', 'chełmski',
                                            'powiat')
    LUBELSKIE_CHELMSKI_WOJSLAWICE_WIEJSKA = ('0603132', 'Wojsławice', GminaType.WIEJSKA, 'lubelskie', 'chełmski',
                                             'powiat')
    LUBELSKIE_CHELMSKI_ZMUDZ_WIEJSKA = ('0603142', 'Żmudź', GminaType.WIEJSKA, 'lubelskie', 'chełmski', 'powiat')
    LUBELSKIE_CHELMSKI_REJOWIEC_MIEJSKO_WIEJSKA = ('0603153', 'Rejowiec', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                   'chełmski', 'powiat')
    LUBELSKIE_HRUBIESZOWSKI_HRUBIESZOW_MIEJSKA = ('0604011', 'Hrubieszów', GminaType.MIEJSKA, 'lubelskie',
                                                  'hrubieszowski', 'powiat')
    LUBELSKIE_HRUBIESZOWSKI_DOLHOBYCZOW_WIEJSKA = ('0604022', 'Dołhobyczów', GminaType.WIEJSKA, 'lubelskie',
                                                   'hrubieszowski', 'powiat')
    LUBELSKIE_HRUBIESZOWSKI_HORODLO_WIEJSKA = ('0604032', 'Horodło', GminaType.WIEJSKA, 'lubelskie', 'hrubieszowski',
                                               'powiat')
    LUBELSKIE_HRUBIESZOWSKI_HRUBIESZOW_WIEJSKA = ('0604042', 'Hrubieszów', GminaType.WIEJSKA, 'lubelskie',
                                                  'hrubieszowski', 'powiat')
    LUBELSKIE_HRUBIESZOWSKI_MIRCZE_WIEJSKA = ('0604052', 'Mircze', GminaType.WIEJSKA, 'lubelskie', 'hrubieszowski',
                                              'powiat')
    LUBELSKIE_HRUBIESZOWSKI_TRZESZCZANY_WIEJSKA = ('0604062', 'Trzeszczany', GminaType.WIEJSKA, 'lubelskie',
                                                   'hrubieszowski', 'powiat')
    LUBELSKIE_HRUBIESZOWSKI_UCHANIE_WIEJSKA = ('0604072', 'Uchanie', GminaType.WIEJSKA, 'lubelskie', 'hrubieszowski',
                                               'powiat')
    LUBELSKIE_HRUBIESZOWSKI_WERBKOWICE_WIEJSKA = ('0604082', 'Werbkowice', GminaType.WIEJSKA, 'lubelskie',
                                                  'hrubieszowski', 'powiat')
    LUBELSKIE_JANOWSKI_BATORZ_WIEJSKA = ('0605012', 'Batorz', GminaType.WIEJSKA, 'lubelskie', 'janowski', 'powiat')
    LUBELSKIE_JANOWSKI_CHRZANOW_WIEJSKA = ('0605022', 'Chrzanów', GminaType.WIEJSKA, 'lubelskie', 'janowski', 'powiat')
    LUBELSKIE_JANOWSKI_DZWOLA_WIEJSKA = ('0605032', 'Dzwola', GminaType.WIEJSKA, 'lubelskie', 'janowski', 'powiat')
    LUBELSKIE_JANOWSKI_GODZISZOW_WIEJSKA = ('0605042', 'Godziszów', GminaType.WIEJSKA, 'lubelskie', 'janowski',
                                            'powiat')
    LUBELSKIE_JANOWSKI_JANOW_LUBELSKI_MIEJSKO_WIEJSKA = ('0605053', 'Janów Lubelski', GminaType.MIEJSKO_WIEJSKA,
                                                         'lubelskie', 'janowski', 'powiat')
    LUBELSKIE_JANOWSKI_MODLIBORZYCE_MIEJSKO_WIEJSKA = ('0605063', 'Modliborzyce', GminaType.MIEJSKO_WIEJSKA,
                                                       'lubelskie', 'janowski', 'powiat')
    LUBELSKIE_JANOWSKI_POTOK_WIELKI_WIEJSKA = ('0605072', 'Potok Wielki', GminaType.WIEJSKA, 'lubelskie', 'janowski',
                                               'powiat')
    LUBELSKIE_KRASNOSTAWSKI_KRASNYSTAW_MIEJSKA = ('0606011', 'Krasnystaw', GminaType.MIEJSKA, 'lubelskie',
                                                  'krasnostawski', 'powiat')
    LUBELSKIE_KRASNOSTAWSKI_FAJSLAWICE_WIEJSKA = ('0606022', 'Fajsławice', GminaType.WIEJSKA, 'lubelskie',
                                                  'krasnostawski', 'powiat')
    LUBELSKIE_KRASNOSTAWSKI_GORZKOW_WIEJSKA = ('0606032', 'Gorzków', GminaType.WIEJSKA, 'lubelskie', 'krasnostawski',
                                               'powiat')
    LUBELSKIE_KRASNOSTAWSKI_IZBICA_MIEJSKO_WIEJSKA = ('0606043', 'Izbica', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                      'krasnostawski', 'powiat')
    LUBELSKIE_KRASNOSTAWSKI_KRASNYSTAW_WIEJSKA = ('0606052', 'Krasnystaw', GminaType.WIEJSKA, 'lubelskie',
                                                  'krasnostawski', 'powiat')
    LUBELSKIE_KRASNOSTAWSKI_KRASNICZYN_WIEJSKA = ('0606062', 'Kraśniczyn', GminaType.WIEJSKA, 'lubelskie',
                                                  'krasnostawski', 'powiat')
    LUBELSKIE_KRASNOSTAWSKI_LOPIENNIK_GORNY_WIEJSKA = ('0606072', 'Łopiennik Górny', GminaType.WIEJSKA, 'lubelskie',
                                                       'krasnostawski', 'powiat')
    LUBELSKIE_KRASNOSTAWSKI_RUDNIK_WIEJSKA = ('0606092', 'Rudnik', GminaType.WIEJSKA, 'lubelskie', 'krasnostawski',
                                              'powiat')
    LUBELSKIE_KRASNOSTAWSKI_SIENNICA_ROZANA_WIEJSKA = ('0606102', 'Siennica Różana', GminaType.WIEJSKA, 'lubelskie',
                                                       'krasnostawski', 'powiat')
    LUBELSKIE_KRASNOSTAWSKI_ZOLKIEWKA_WIEJSKA = ('0606112', 'Żółkiewka', GminaType.WIEJSKA, 'lubelskie',
                                                 'krasnostawski', 'powiat')
    LUBELSKIE_KRASNICKI_KRASNIK_MIEJSKA = ('0607011', 'Kraśnik', GminaType.MIEJSKA, 'lubelskie', 'kraśnicki', 'powiat')
    LUBELSKIE_KRASNICKI_ANNOPOL_MIEJSKO_WIEJSKA = ('0607023', 'Annopol', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                   'kraśnicki', 'powiat')
    LUBELSKIE_KRASNICKI_DZIERZKOWICE_WIEJSKA = ('0607032', 'Dzierzkowice', GminaType.WIEJSKA, 'lubelskie', 'kraśnicki',
                                                'powiat')
    LUBELSKIE_KRASNICKI_GOSCIERADOW_WIEJSKA = ('0607042', 'Gościeradów', GminaType.WIEJSKA, 'lubelskie', 'kraśnicki',
                                               'powiat')
    LUBELSKIE_KRASNICKI_KRASNIK_WIEJSKA = ('0607052', 'Kraśnik', GminaType.WIEJSKA, 'lubelskie', 'kraśnicki', 'powiat')
    LUBELSKIE_KRASNICKI_SZASTARKA_WIEJSKA = ('0607062', 'Szastarka', GminaType.WIEJSKA, 'lubelskie', 'kraśnicki',
                                             'powiat')
    LUBELSKIE_KRASNICKI_TRZYDNIK_DUZY_WIEJSKA = ('0607072', 'Trzydnik Duży', GminaType.WIEJSKA, 'lubelskie',
                                                 'kraśnicki', 'powiat')
    LUBELSKIE_KRASNICKI_URZEDOW_MIEJSKO_WIEJSKA = ('0607083', 'Urzędów', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                   'kraśnicki', 'powiat')
    LUBELSKIE_KRASNICKI_WILKOLAZ_WIEJSKA = ('0607092', 'Wilkołaz', GminaType.WIEJSKA, 'lubelskie', 'kraśnicki',
                                            'powiat')
    LUBELSKIE_KRASNICKI_ZAKRZOWEK_WIEJSKA = ('0607102', 'Zakrzówek', GminaType.WIEJSKA, 'lubelskie', 'kraśnicki',
                                             'powiat')
    LUBELSKIE_LUBARTOWSKI_LUBARTOW_MIEJSKA = ('0608011', 'Lubartów', GminaType.MIEJSKA, 'lubelskie', 'lubartowski',
                                              'powiat')
    LUBELSKIE_LUBARTOWSKI_ABRAMOW_WIEJSKA = ('0608022', 'Abramów', GminaType.WIEJSKA, 'lubelskie', 'lubartowski',
                                             'powiat')
    LUBELSKIE_LUBARTOWSKI_FIRLEJ_WIEJSKA = ('0608032', 'Firlej', GminaType.WIEJSKA, 'lubelskie', 'lubartowski',
                                            'powiat')
    LUBELSKIE_LUBARTOWSKI_JEZIORZANY_WIEJSKA = ('0608042', 'Jeziorzany', GminaType.WIEJSKA, 'lubelskie', 'lubartowski',
                                                'powiat')
    LUBELSKIE_LUBARTOWSKI_KAMIONKA_MIEJSKO_WIEJSKA = ('0608053', 'Kamionka', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                      'lubartowski', 'powiat')
    LUBELSKIE_LUBARTOWSKI_KOCK_MIEJSKO_WIEJSKA = ('0608063', 'Kock', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                  'lubartowski', 'powiat')
    LUBELSKIE_LUBARTOWSKI_LUBARTOW_WIEJSKA = ('0608072', 'Lubartów', GminaType.WIEJSKA, 'lubelskie', 'lubartowski',
                                              'powiat')
    LUBELSKIE_LUBARTOWSKI_MICHOW_WIEJSKA = ('0608082', 'Michów', GminaType.WIEJSKA, 'lubelskie', 'lubartowski',
                                            'powiat')
    LUBELSKIE_LUBARTOWSKI_NIEDZWIADA_WIEJSKA = ('0608092', 'Niedźwiada', GminaType.WIEJSKA, 'lubelskie', 'lubartowski',
                                                'powiat')
    LUBELSKIE_LUBARTOWSKI_OSTROW_LUBELSKI_MIEJSKO_WIEJSKA = ('0608103', 'Ostrów Lubelski', GminaType.MIEJSKO_WIEJSKA,
                                                             'lubelskie', 'lubartowski', 'powiat')
    LUBELSKIE_LUBARTOWSKI_OSTROWEK_WIEJSKA = ('0608112', 'Ostrówek', GminaType.WIEJSKA, 'lubelskie', 'lubartowski',
                                              'powiat')
    LUBELSKIE_LUBARTOWSKI_SERNIKI_WIEJSKA = ('0608122', 'Serniki', GminaType.WIEJSKA, 'lubelskie', 'lubartowski',
                                             'powiat')
    LUBELSKIE_LUBARTOWSKI_USCIMOW_WIEJSKA = ('0608132', 'Uścimów', GminaType.WIEJSKA, 'lubelskie', 'lubartowski',
                                             'powiat')
    LUBELSKIE_LUBELSKI_BELZYCE_MIEJSKO_WIEJSKA = ('0609013', 'Bełżyce', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                  'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_BORZECHOW_WIEJSKA = ('0609022', 'Borzechów', GminaType.WIEJSKA, 'lubelskie', 'lubelski',
                                            'powiat')
    LUBELSKIE_LUBELSKI_BYCHAWA_MIEJSKO_WIEJSKA = ('0609033', 'Bychawa', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                  'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_GARBOW_WIEJSKA = ('0609042', 'Garbów', GminaType.WIEJSKA, 'lubelskie', 'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_GLUSK_WIEJSKA = ('0609052', 'Głusk', GminaType.WIEJSKA, 'lubelskie', 'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_JABLONNA_WIEJSKA = ('0609062', 'Jabłonna', GminaType.WIEJSKA, 'lubelskie', 'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_JASTKOW_WIEJSKA = ('0609072', 'Jastków', GminaType.WIEJSKA, 'lubelskie', 'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_KONOPNICA_WIEJSKA = ('0609082', 'Konopnica', GminaType.WIEJSKA, 'lubelskie', 'lubelski',
                                            'powiat')
    LUBELSKIE_LUBELSKI_KRZCZONOW_WIEJSKA = ('0609092', 'Krzczonów', GminaType.WIEJSKA, 'lubelskie', 'lubelski',
                                            'powiat')
    LUBELSKIE_LUBELSKI_NIEDRZWICA_DUZA_WIEJSKA = ('0609102', 'Niedrzwica Duża', GminaType.WIEJSKA, 'lubelskie',
                                                  'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_NIEMCE_WIEJSKA = ('0609112', 'Niemce', GminaType.WIEJSKA, 'lubelskie', 'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_STRZYZEWICE_WIEJSKA = ('0609122', 'Strzyżewice', GminaType.WIEJSKA, 'lubelskie', 'lubelski',
                                              'powiat')
    LUBELSKIE_LUBELSKI_WOJCIECHOW_WIEJSKA = ('0609132', 'Wojciechów', GminaType.WIEJSKA, 'lubelskie', 'lubelski',
                                             'powiat')
    LUBELSKIE_LUBELSKI_WOLKA_WIEJSKA = ('0609142', 'Wólka', GminaType.WIEJSKA, 'lubelskie', 'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_WYSOKIE_WIEJSKA = ('0609152', 'Wysokie', GminaType.WIEJSKA, 'lubelskie', 'lubelski', 'powiat')
    LUBELSKIE_LUBELSKI_ZAKRZEW_WIEJSKA = ('0609162', 'Zakrzew', GminaType.WIEJSKA, 'lubelskie', 'lubelski', 'powiat')
    LUBELSKIE_LECZYNSKI_CYCOW_WIEJSKA = ('0610012', 'Cyców', GminaType.WIEJSKA, 'lubelskie', 'łęczyński', 'powiat')
    LUBELSKIE_LECZYNSKI_LUDWIN_WIEJSKA = ('0610022', 'Ludwin', GminaType.WIEJSKA, 'lubelskie', 'łęczyński', 'powiat')
    LUBELSKIE_LECZYNSKI_LECZNA_MIEJSKO_WIEJSKA = ('0610033', 'Łęczna', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                  'łęczyński', 'powiat')
    LUBELSKIE_LECZYNSKI_MILEJOW_WIEJSKA = ('0610042', 'Milejów', GminaType.WIEJSKA, 'lubelskie', 'łęczyński', 'powiat')
    LUBELSKIE_LECZYNSKI_PUCHACZOW_WIEJSKA = ('0610052', 'Puchaczów', GminaType.WIEJSKA, 'lubelskie', 'łęczyński',
                                             'powiat')
    LUBELSKIE_LECZYNSKI_SPICZYN_WIEJSKA = ('0610062', 'Spiczyn', GminaType.WIEJSKA, 'lubelskie', 'łęczyński', 'powiat')
    LUBELSKIE_LUKOWSKI_LUKOW_MIEJSKA = ('0611011', 'Łuków', GminaType.MIEJSKA, 'lubelskie', 'łukowski', 'powiat')
    LUBELSKIE_LUKOWSKI_STOCZEK_LUKOWSKI_MIEJSKA = ('0611021', 'Stoczek Łukowski', GminaType.MIEJSKA, 'lubelskie',
                                                   'łukowski', 'powiat')
    LUBELSKIE_LUKOWSKI_ADAMOW_WIEJSKA = ('0611032', 'Adamów', GminaType.WIEJSKA, 'lubelskie', 'łukowski', 'powiat')
    LUBELSKIE_LUKOWSKI_KRZYWDA_WIEJSKA = ('0611042', 'Krzywda', GminaType.WIEJSKA, 'lubelskie', 'łukowski', 'powiat')
    LUBELSKIE_LUKOWSKI_LUKOW_WIEJSKA = ('0611052', 'Łuków', GminaType.WIEJSKA, 'lubelskie', 'łukowski', 'powiat')
    LUBELSKIE_LUKOWSKI_SEROKOMLA_WIEJSKA = ('0611062', 'Serokomla', GminaType.WIEJSKA, 'lubelskie', 'łukowski',
                                            'powiat')
    LUBELSKIE_LUKOWSKI_STANIN_WIEJSKA = ('0611072', 'Stanin', GminaType.WIEJSKA, 'lubelskie', 'łukowski', 'powiat')
    LUBELSKIE_LUKOWSKI_STOCZEK_LUKOWSKI_WIEJSKA = ('0611082', 'Stoczek Łukowski', GminaType.WIEJSKA, 'lubelskie',
                                                   'łukowski', 'powiat')
    LUBELSKIE_LUKOWSKI_TRZEBIESZOW_WIEJSKA = ('0611092', 'Trzebieszów', GminaType.WIEJSKA, 'lubelskie', 'łukowski',
                                              'powiat')
    LUBELSKIE_LUKOWSKI_WOJCIESZKOW_WIEJSKA = ('0611102', 'Wojcieszków', GminaType.WIEJSKA, 'lubelskie', 'łukowski',
                                              'powiat')
    LUBELSKIE_LUKOWSKI_WOLA_MYSLOWSKA_WIEJSKA = ('0611112', 'Wola Mysłowska', GminaType.WIEJSKA, 'lubelskie',
                                                 'łukowski', 'powiat')
    LUBELSKIE_OPOLSKI_CHODEL_WIEJSKA = ('0612012', 'Chodel', GminaType.WIEJSKA, 'lubelskie', 'opolski', 'powiat')
    LUBELSKIE_OPOLSKI_JOZEFOW_NAD_WISLA_MIEJSKO_WIEJSKA = ('0612023', 'Józefów nad Wisłą', GminaType.MIEJSKO_WIEJSKA,
                                                           'lubelskie', 'opolski', 'powiat')
    LUBELSKIE_OPOLSKI_KARCZMISKA_WIEJSKA = ('0612032', 'Karczmiska', GminaType.WIEJSKA, 'lubelskie', 'opolski',
                                            'powiat')
    LUBELSKIE_OPOLSKI_LAZISKA_WIEJSKA = ('0612042', 'Łaziska', GminaType.WIEJSKA, 'lubelskie', 'opolski', 'powiat')
    LUBELSKIE_OPOLSKI_OPOLE_LUBELSKIE_MIEJSKO_WIEJSKA = ('0612053', 'Opole Lubelskie', GminaType.MIEJSKO_WIEJSKA,
                                                         'lubelskie', 'opolski', 'powiat')
    LUBELSKIE_OPOLSKI_PONIATOWA_MIEJSKO_WIEJSKA = ('0612063', 'Poniatowa', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                   'opolski', 'powiat')
    LUBELSKIE_OPOLSKI_WILKOW_WIEJSKA = ('0612072', 'Wilków', GminaType.WIEJSKA, 'lubelskie', 'opolski', 'powiat')
    LUBELSKIE_PARCZEWSKI_DEBOWA_KLODA_WIEJSKA = ('0613012', 'Dębowa Kłoda', GminaType.WIEJSKA, 'lubelskie',
                                                 'parczewski', 'powiat')
    LUBELSKIE_PARCZEWSKI_JABLON_WIEJSKA = ('0613022', 'Jabłoń', GminaType.WIEJSKA, 'lubelskie', 'parczewski', 'powiat')
    LUBELSKIE_PARCZEWSKI_MILANOW_WIEJSKA = ('0613032', 'Milanów', GminaType.WIEJSKA, 'lubelskie', 'parczewski',
                                            'powiat')
    LUBELSKIE_PARCZEWSKI_PARCZEW_MIEJSKO_WIEJSKA = ('0613043', 'Parczew', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                    'parczewski', 'powiat')
    LUBELSKIE_PARCZEWSKI_PODEDWORZE_WIEJSKA = ('0613052', 'Podedwórze', GminaType.WIEJSKA, 'lubelskie', 'parczewski',
                                               'powiat')
    LUBELSKIE_PARCZEWSKI_SIEMIEN_WIEJSKA = ('0613062', 'Siemień', GminaType.WIEJSKA, 'lubelskie', 'parczewski',
                                            'powiat')
    LUBELSKIE_PARCZEWSKI_SOSNOWICA_WIEJSKA = ('0613072', 'Sosnowica', GminaType.WIEJSKA, 'lubelskie', 'parczewski',
                                              'powiat')
    LUBELSKIE_PULAWSKI_PULAWY_MIEJSKA = ('0614011', 'Puławy', GminaType.MIEJSKA, 'lubelskie', 'puławski', 'powiat')
    LUBELSKIE_PULAWSKI_BARANOW_WIEJSKA = ('0614022', 'Baranów', GminaType.WIEJSKA, 'lubelskie', 'puławski', 'powiat')
    LUBELSKIE_PULAWSKI_JANOWIEC_WIEJSKA = ('0614032', 'Janowiec', GminaType.WIEJSKA, 'lubelskie', 'puławski', 'powiat')
    LUBELSKIE_PULAWSKI_KAZIMIERZ_DOLNY_MIEJSKO_WIEJSKA = ('0614043', 'Kazimierz Dolny', GminaType.MIEJSKO_WIEJSKA,
                                                          'lubelskie', 'puławski', 'powiat')
    LUBELSKIE_PULAWSKI_KONSKOWOLA_MIEJSKO_WIEJSKA = ('0614053', 'Końskowola', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                     'puławski', 'powiat')
    LUBELSKIE_PULAWSKI_KUROW_MIEJSKO_WIEJSKA = ('0614063', 'Kurów', GminaType.MIEJSKO_WIEJSKA, 'lubelskie', 'puławski',
                                                'powiat')
    LUBELSKIE_PULAWSKI_MARKUSZOW_WIEJSKA = ('0614072', 'Markuszów', GminaType.WIEJSKA, 'lubelskie', 'puławski',
                                            'powiat')
    LUBELSKIE_PULAWSKI_NALECZOW_MIEJSKO_WIEJSKA = ('0614083', 'Nałęczów', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                   'puławski', 'powiat')
    LUBELSKIE_PULAWSKI_PULAWY_WIEJSKA = ('0614092', 'Puławy', GminaType.WIEJSKA, 'lubelskie', 'puławski', 'powiat')
    LUBELSKIE_PULAWSKI_WAWOLNICA_MIEJSKO_WIEJSKA = ('0614103', 'Wąwolnica', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                    'puławski', 'powiat')
    LUBELSKIE_PULAWSKI_ZYRZYN_WIEJSKA = ('0614112', 'Żyrzyn', GminaType.WIEJSKA, 'lubelskie', 'puławski', 'powiat')
    LUBELSKIE_RADZYNSKI_RADZYN_PODLASKI_MIEJSKA = ('0615011', 'Radzyń Podlaski', GminaType.MIEJSKA, 'lubelskie',
                                                   'radzyński', 'powiat')
    LUBELSKIE_RADZYNSKI_BORKI_WIEJSKA = ('0615022', 'Borki', GminaType.WIEJSKA, 'lubelskie', 'radzyński', 'powiat')
    LUBELSKIE_RADZYNSKI_CZEMIERNIKI_MIEJSKO_WIEJSKA = ('0615033', 'Czemierniki', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                       'radzyński', 'powiat')
    LUBELSKIE_RADZYNSKI_KAKOLEWNICA_WIEJSKA = ('0615042', 'Kąkolewnica', GminaType.WIEJSKA, 'lubelskie', 'radzyński',
                                               'powiat')
    LUBELSKIE_RADZYNSKI_KOMAROWKA_PODLASKA_WIEJSKA = ('0615052', 'Komarówka Podlaska', GminaType.WIEJSKA, 'lubelskie',
                                                      'radzyński', 'powiat')
    LUBELSKIE_RADZYNSKI_RADZYN_PODLASKI_WIEJSKA = ('0615062', 'Radzyń Podlaski', GminaType.WIEJSKA, 'lubelskie',
                                                   'radzyński', 'powiat')
    LUBELSKIE_RADZYNSKI_ULAN_MAJORAT_WIEJSKA = ('0615072', 'Ulan-Majorat', GminaType.WIEJSKA, 'lubelskie', 'radzyński',
                                                'powiat')
    LUBELSKIE_RADZYNSKI_WOHYN_WIEJSKA = ('0615082', 'Wohyń', GminaType.WIEJSKA, 'lubelskie', 'radzyński', 'powiat')
    LUBELSKIE_RYCKI_DEBLIN_MIEJSKA = ('0616011', 'Dęblin', GminaType.MIEJSKA, 'lubelskie', 'rycki', 'powiat')
    LUBELSKIE_RYCKI_KLOCZEW_WIEJSKA = ('0616022', 'Kłoczew', GminaType.WIEJSKA, 'lubelskie', 'rycki', 'powiat')
    LUBELSKIE_RYCKI_NOWODWOR_WIEJSKA = ('0616032', 'Nowodwór', GminaType.WIEJSKA, 'lubelskie', 'rycki', 'powiat')
    LUBELSKIE_RYCKI_RYKI_MIEJSKO_WIEJSKA = ('0616043', 'Ryki', GminaType.MIEJSKO_WIEJSKA, 'lubelskie', 'rycki',
                                            'powiat')
    LUBELSKIE_RYCKI_STEZYCA_WIEJSKA = ('0616052', 'Stężyca', GminaType.WIEJSKA, 'lubelskie', 'rycki', 'powiat')
    LUBELSKIE_RYCKI_ULEZ_WIEJSKA = ('0616062', 'Ułęż', GminaType.WIEJSKA, 'lubelskie', 'rycki', 'powiat')
    LUBELSKIE_SWIDNICKI_SWIDNIK_MIEJSKA = ('0617011', 'Świdnik', GminaType.MIEJSKA, 'lubelskie', 'świdnicki', 'powiat')
    LUBELSKIE_SWIDNICKI_MELGIEW_WIEJSKA = ('0617022', 'Mełgiew', GminaType.WIEJSKA, 'lubelskie', 'świdnicki', 'powiat')
    LUBELSKIE_SWIDNICKI_PIASKI_MIEJSKO_WIEJSKA = ('0617033', 'Piaski', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                  'świdnicki', 'powiat')
    LUBELSKIE_SWIDNICKI_RYBCZEWICE_WIEJSKA = ('0617042', 'Rybczewice', GminaType.WIEJSKA, 'lubelskie', 'świdnicki',
                                              'powiat')
    LUBELSKIE_SWIDNICKI_TRAWNIKI_WIEJSKA = ('0617052', 'Trawniki', GminaType.WIEJSKA, 'lubelskie', 'świdnicki',
                                            'powiat')
    LUBELSKIE_TOMASZOWSKI_TOMASZOW_LUBELSKI_MIEJSKA = ('0618011', 'Tomaszów Lubelski', GminaType.MIEJSKA, 'lubelskie',
                                                       'tomaszowski', 'powiat')
    LUBELSKIE_TOMASZOWSKI_BELZEC_WIEJSKA = ('0618022', 'Bełżec', GminaType.WIEJSKA, 'lubelskie', 'tomaszowski',
                                            'powiat')
    LUBELSKIE_TOMASZOWSKI_JARCZOW_WIEJSKA = ('0618032', 'Jarczów', GminaType.WIEJSKA, 'lubelskie', 'tomaszowski',
                                             'powiat')
    LUBELSKIE_TOMASZOWSKI_KRYNICE_WIEJSKA = ('0618042', 'Krynice', GminaType.WIEJSKA, 'lubelskie', 'tomaszowski',
                                             'powiat')
    LUBELSKIE_TOMASZOWSKI_LUBYCZA_KROLEWSKA_MIEJSKO_WIEJSKA = ('0618053', 'Lubycza Królewska',
                                                               GminaType.MIEJSKO_WIEJSKA, 'lubelskie', 'tomaszowski',
                                                               'powiat')
    LUBELSKIE_TOMASZOWSKI_LASZCZOW_MIEJSKO_WIEJSKA = ('0618063', 'Łaszczów', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                      'tomaszowski', 'powiat')
    LUBELSKIE_TOMASZOWSKI_RACHANIE_WIEJSKA = ('0618072', 'Rachanie', GminaType.WIEJSKA, 'lubelskie', 'tomaszowski',
                                              'powiat')
    LUBELSKIE_TOMASZOWSKI_SUSIEC_WIEJSKA = ('0618082', 'Susiec', GminaType.WIEJSKA, 'lubelskie', 'tomaszowski',
                                            'powiat')
    LUBELSKIE_TOMASZOWSKI_TARNAWATKA_WIEJSKA = ('0618092', 'Tarnawatka', GminaType.WIEJSKA, 'lubelskie', 'tomaszowski',
                                                'powiat')
    LUBELSKIE_TOMASZOWSKI_TELATYN_WIEJSKA = ('0618102', 'Telatyn', GminaType.WIEJSKA, 'lubelskie', 'tomaszowski',
                                             'powiat')
    LUBELSKIE_TOMASZOWSKI_TOMASZOW_LUBELSKI_WIEJSKA = ('0618112', 'Tomaszów Lubelski', GminaType.WIEJSKA, 'lubelskie',
                                                       'tomaszowski', 'powiat')
    LUBELSKIE_TOMASZOWSKI_TYSZOWCE_MIEJSKO_WIEJSKA = ('0618123', 'Tyszowce', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                      'tomaszowski', 'powiat')
    LUBELSKIE_TOMASZOWSKI_ULHOWEK_WIEJSKA = ('0618132', 'Ulhówek', GminaType.WIEJSKA, 'lubelskie', 'tomaszowski',
                                             'powiat')
    LUBELSKIE_WLODAWSKI_WLODAWA_MIEJSKA = ('0619011', 'Włodawa', GminaType.MIEJSKA, 'lubelskie', 'włodawski', 'powiat')
    LUBELSKIE_WLODAWSKI_HANNA_WIEJSKA = ('0619022', 'Hanna', GminaType.WIEJSKA, 'lubelskie', 'włodawski', 'powiat')
    LUBELSKIE_WLODAWSKI_HANSK_WIEJSKA = ('0619032', 'Hańsk', GminaType.WIEJSKA, 'lubelskie', 'włodawski', 'powiat')
    LUBELSKIE_WLODAWSKI_STARY_BRUS_WIEJSKA = ('0619042', 'Stary Brus', GminaType.WIEJSKA, 'lubelskie', 'włodawski',
                                              'powiat')
    LUBELSKIE_WLODAWSKI_URSZULIN_WIEJSKA = ('0619052', 'Urszulin', GminaType.WIEJSKA, 'lubelskie', 'włodawski',
                                            'powiat')
    LUBELSKIE_WLODAWSKI_WLODAWA_WIEJSKA = ('0619062', 'Włodawa', GminaType.WIEJSKA, 'lubelskie', 'włodawski', 'powiat')
    LUBELSKIE_WLODAWSKI_WOLA_UHRUSKA_WIEJSKA = ('0619072', 'Wola Uhruska', GminaType.WIEJSKA, 'lubelskie', 'włodawski',
                                                'powiat')
    LUBELSKIE_WLODAWSKI_WYRYKI_WIEJSKA = ('0619082', 'Wyryki', GminaType.WIEJSKA, 'lubelskie', 'włodawski', 'powiat')
    LUBELSKIE_ZAMOJSKI_ADAMOW_WIEJSKA = ('0620012', 'Adamów', GminaType.WIEJSKA, 'lubelskie', 'zamojski', 'powiat')
    LUBELSKIE_ZAMOJSKI_GRABOWIEC_WIEJSKA = ('0620022', 'Grabowiec', GminaType.WIEJSKA, 'lubelskie', 'zamojski',
                                            'powiat')
    LUBELSKIE_ZAMOJSKI_KOMAROW_OSADA_WIEJSKA = ('0620032', 'Komarów-Osada', GminaType.WIEJSKA, 'lubelskie', 'zamojski',
                                                'powiat')
    LUBELSKIE_ZAMOJSKI_KRASNOBROD_MIEJSKO_WIEJSKA = ('0620043', 'Krasnobród', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                     'zamojski', 'powiat')
    LUBELSKIE_ZAMOJSKI_LABUNIE_WIEJSKA = ('0620052', 'Łabunie', GminaType.WIEJSKA, 'lubelskie', 'zamojski', 'powiat')
    LUBELSKIE_ZAMOJSKI_MIACZYN_WIEJSKA = ('0620062', 'Miączyn', GminaType.WIEJSKA, 'lubelskie', 'zamojski', 'powiat')
    LUBELSKIE_ZAMOJSKI_NIELISZ_WIEJSKA = ('0620072', 'Nielisz', GminaType.WIEJSKA, 'lubelskie', 'zamojski', 'powiat')
    LUBELSKIE_ZAMOJSKI_RADECZNICA_WIEJSKA = ('0620082', 'Radecznica', GminaType.WIEJSKA, 'lubelskie', 'zamojski',
                                             'powiat')
    LUBELSKIE_ZAMOJSKI_SITNO_WIEJSKA = ('0620092', 'Sitno', GminaType.WIEJSKA, 'lubelskie', 'zamojski', 'powiat')
    LUBELSKIE_ZAMOJSKI_SKIERBIESZOW_WIEJSKA = ('0620102', 'Skierbieszów', GminaType.WIEJSKA, 'lubelskie', 'zamojski',
                                               'powiat')
    LUBELSKIE_ZAMOJSKI_STARY_ZAMOSC_WIEJSKA = ('0620112', 'Stary Zamość', GminaType.WIEJSKA, 'lubelskie', 'zamojski',
                                               'powiat')
    LUBELSKIE_ZAMOJSKI_SULOW_WIEJSKA = ('0620122', 'Sułów', GminaType.WIEJSKA, 'lubelskie', 'zamojski', 'powiat')
    LUBELSKIE_ZAMOJSKI_SZCZEBRZESZYN_MIEJSKO_WIEJSKA = ('0620133', 'Szczebrzeszyn', GminaType.MIEJSKO_WIEJSKA,
                                                        'lubelskie', 'zamojski', 'powiat')
    LUBELSKIE_ZAMOJSKI_ZAMOSC_WIEJSKA = ('0620142', 'Zamość', GminaType.WIEJSKA, 'lubelskie', 'zamojski', 'powiat')
    LUBELSKIE_ZAMOJSKI_ZWIERZYNIEC_MIEJSKO_WIEJSKA = ('0620153', 'Zwierzyniec', GminaType.MIEJSKO_WIEJSKA, 'lubelskie',
                                                      'zamojski', 'powiat')
    LUBELSKIE_BIALA_PODLASKA_BIALA_PODLASKA_MIEJSKA = ('0661011', 'Biała Podlaska', GminaType.MIEJSKA, 'lubelskie',
                                                       'Biała Podlaska', 'miasto na prawach powiatu')
    LUBELSKIE_CHELM_CHELM_MIEJSKA = ('0662011', 'Chełm', GminaType.MIEJSKA, 'lubelskie', 'Chełm',
                                     'miasto na prawach powiatu')
    LUBELSKIE_LUBLIN_LUBLIN_MIEJSKA = ('0663011', 'Lublin', GminaType.MIEJSKA, 'lubelskie', 'Lublin',
                                       'miasto na prawach powiatu')
    LUBELSKIE_ZAMOSC_ZAMOSC_MIEJSKA = ('0664011', 'Zamość', GminaType.MIEJSKA, 'lubelskie', 'Zamość',
                                       'miasto na prawach powiatu')

    # Lubuskie
    LUBUSKIE_GORZOWSKI_KOSTRZYN_NAD_ODRA_MIEJSKA = ('0801011', 'Kostrzyn nad Odrą', GminaType.MIEJSKA, 'lubuskie',
                                                    'gorzowski', 'powiat')
    LUBUSKIE_GORZOWSKI_BOGDANIEC_WIEJSKA = ('0801022', 'Bogdaniec', GminaType.WIEJSKA, 'lubuskie', 'gorzowski',
                                            'powiat')
    LUBUSKIE_GORZOWSKI_DESZCZNO_WIEJSKA = ('0801032', 'Deszczno', GminaType.WIEJSKA, 'lubuskie', 'gorzowski', 'powiat')
    LUBUSKIE_GORZOWSKI_KLODAWA_WIEJSKA = ('0801042', 'Kłodawa', GminaType.WIEJSKA, 'lubuskie', 'gorzowski', 'powiat')
    LUBUSKIE_GORZOWSKI_LUBISZYN_WIEJSKA = ('0801052', 'Lubiszyn', GminaType.WIEJSKA, 'lubuskie', 'gorzowski', 'powiat')
    LUBUSKIE_GORZOWSKI_SANTOK_WIEJSKA = ('0801062', 'Santok', GminaType.WIEJSKA, 'lubuskie', 'gorzowski', 'powiat')
    LUBUSKIE_GORZOWSKI_WITNICA_MIEJSKO_WIEJSKA = ('0801073', 'Witnica', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                  'gorzowski', 'powiat')
    LUBUSKIE_KROSNIENSKI_GUBIN_MIEJSKA = ('0802011', 'Gubin', GminaType.MIEJSKA, 'lubuskie', 'krośnieński', 'powiat')
    LUBUSKIE_KROSNIENSKI_BOBROWICE_WIEJSKA = ('0802022', 'Bobrowice', GminaType.WIEJSKA, 'lubuskie', 'krośnieński',
                                              'powiat')
    LUBUSKIE_KROSNIENSKI_BYTNICA_WIEJSKA = ('0802032', 'Bytnica', GminaType.WIEJSKA, 'lubuskie', 'krośnieński',
                                            'powiat')
    LUBUSKIE_KROSNIENSKI_DABIE_WIEJSKA = ('0802042', 'Dąbie', GminaType.WIEJSKA, 'lubuskie', 'krośnieński', 'powiat')
    LUBUSKIE_KROSNIENSKI_GUBIN_WIEJSKA = ('0802052', 'Gubin', GminaType.WIEJSKA, 'lubuskie', 'krośnieński', 'powiat')
    LUBUSKIE_KROSNIENSKI_KROSNO_ODRZANSKIE_MIEJSKO_WIEJSKA = ('0802063', 'Krosno Odrzańskie', GminaType.MIEJSKO_WIEJSKA,
                                                              'lubuskie', 'krośnieński', 'powiat')
    LUBUSKIE_KROSNIENSKI_MASZEWO_WIEJSKA = ('0802072', 'Maszewo', GminaType.WIEJSKA, 'lubuskie', 'krośnieński',
                                            'powiat')
    LUBUSKIE_MIEDZYRZECKI_BLEDZEW_WIEJSKA = ('0803012', 'Bledzew', GminaType.WIEJSKA, 'lubuskie', 'międzyrzecki',
                                             'powiat')
    LUBUSKIE_MIEDZYRZECKI_MIEDZYRZECZ_MIEJSKO_WIEJSKA = ('0803023', 'Międzyrzecz', GminaType.MIEJSKO_WIEJSKA,
                                                         'lubuskie', 'międzyrzecki', 'powiat')
    LUBUSKIE_MIEDZYRZECKI_PRZYTOCZNA_WIEJSKA = ('0803032', 'Przytoczna', GminaType.WIEJSKA, 'lubuskie', 'międzyrzecki',
                                                'powiat')
    LUBUSKIE_MIEDZYRZECKI_PSZCZEW_WIEJSKA = ('0803042', 'Pszczew', GminaType.WIEJSKA, 'lubuskie', 'międzyrzecki',
                                             'powiat')
    LUBUSKIE_MIEDZYRZECKI_SKWIERZYNA_MIEJSKO_WIEJSKA = ('0803053', 'Skwierzyna', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                        'międzyrzecki', 'powiat')
    LUBUSKIE_MIEDZYRZECKI_TRZCIEL_MIEJSKO_WIEJSKA = ('0803063', 'Trzciel', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                     'międzyrzecki', 'powiat')
    LUBUSKIE_NOWOSOLSKI_NOWA_SOL_MIEJSKA = ('0804011', 'Nowa Sól', GminaType.MIEJSKA, 'lubuskie', 'nowosolski',
                                            'powiat')
    LUBUSKIE_NOWOSOLSKI_BYTOM_ODRZANSKI_MIEJSKO_WIEJSKA = ('0804023', 'Bytom Odrzański', GminaType.MIEJSKO_WIEJSKA,
                                                           'lubuskie', 'nowosolski', 'powiat')
    LUBUSKIE_NOWOSOLSKI_KOLSKO_WIEJSKA = ('0804032', 'Kolsko', GminaType.WIEJSKA, 'lubuskie', 'nowosolski', 'powiat')
    LUBUSKIE_NOWOSOLSKI_KOZUCHOW_MIEJSKO_WIEJSKA = ('0804043', 'Kożuchów', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                    'nowosolski', 'powiat')
    LUBUSKIE_NOWOSOLSKI_NOWA_SOL_WIEJSKA = ('0804052', 'Nowa Sól', GminaType.WIEJSKA, 'lubuskie', 'nowosolski',
                                            'powiat')
    LUBUSKIE_NOWOSOLSKI_NOWE_MIASTECZKO_MIEJSKO_WIEJSKA = ('0804063', 'Nowe Miasteczko', GminaType.MIEJSKO_WIEJSKA,
                                                           'lubuskie', 'nowosolski', 'powiat')
    LUBUSKIE_NOWOSOLSKI_OTYN_MIEJSKO_WIEJSKA = ('0804073', 'Otyń', GminaType.MIEJSKO_WIEJSKA, 'lubuskie', 'nowosolski',
                                                'powiat')
    LUBUSKIE_NOWOSOLSKI_SIEDLISKO_WIEJSKA = ('0804082', 'Siedlisko', GminaType.WIEJSKA, 'lubuskie', 'nowosolski',
                                             'powiat')
    LUBUSKIE_SLUBICKI_CYBINKA_MIEJSKO_WIEJSKA = ('0805013', 'Cybinka', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                 'słubicki', 'powiat')
    LUBUSKIE_SLUBICKI_GORZYCA_WIEJSKA = ('0805022', 'Górzyca', GminaType.WIEJSKA, 'lubuskie', 'słubicki', 'powiat')
    LUBUSKIE_SLUBICKI_OSNO_LUBUSKIE_MIEJSKO_WIEJSKA = ('0805033', 'Ośno Lubuskie', GminaType.MIEJSKO_WIEJSKA,
                                                       'lubuskie', 'słubicki', 'powiat')
    LUBUSKIE_SLUBICKI_RZEPIN_MIEJSKO_WIEJSKA = ('0805043', 'Rzepin', GminaType.MIEJSKO_WIEJSKA, 'lubuskie', 'słubicki',
                                                'powiat')
    LUBUSKIE_SLUBICKI_SLUBICE_MIEJSKO_WIEJSKA = ('0805053', 'Słubice', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                 'słubicki', 'powiat')
    LUBUSKIE_STRZELECKO_DREZDENECKI_DOBIEGNIEW_MIEJSKO_WIEJSKA = ('0806013', 'Dobiegniew', GminaType.MIEJSKO_WIEJSKA,
                                                                  'lubuskie', 'strzelecko-drezdenecki', 'powiat')
    LUBUSKIE_STRZELECKO_DREZDENECKI_DREZDENKO_MIEJSKO_WIEJSKA = ('0806023', 'Drezdenko', GminaType.MIEJSKO_WIEJSKA,
                                                                 'lubuskie', 'strzelecko-drezdenecki', 'powiat')
    LUBUSKIE_STRZELECKO_DREZDENECKI_STARE_KUROWO_WIEJSKA = ('0806032', 'Stare Kurowo', GminaType.WIEJSKA, 'lubuskie',
                                                            'strzelecko-drezdenecki', 'powiat')
    LUBUSKIE_STRZELECKO_DREZDENECKI_STRZELCE_KRAJENSKIE_MIEJSKO_WIEJSKA = ('0806043', 'Strzelce Krajeńskie',
                                                                           GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                                           'strzelecko-drezdenecki', 'powiat')
    LUBUSKIE_STRZELECKO_DREZDENECKI_ZWIERZYN_WIEJSKA = ('0806052', 'Zwierzyn', GminaType.WIEJSKA, 'lubuskie',
                                                        'strzelecko-drezdenecki', 'powiat')
    LUBUSKIE_SULECINSKI_KRZESZYCE_WIEJSKA = ('0807012', 'Krzeszyce', GminaType.WIEJSKA, 'lubuskie', 'sulęciński',
                                             'powiat')
    LUBUSKIE_SULECINSKI_LUBNIEWICE_MIEJSKO_WIEJSKA = ('0807023', 'Lubniewice', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                      'sulęciński', 'powiat')
    LUBUSKIE_SULECINSKI_SLONSK_WIEJSKA = ('0807032', 'Słońsk', GminaType.WIEJSKA, 'lubuskie', 'sulęciński', 'powiat')
    LUBUSKIE_SULECINSKI_SULECIN_MIEJSKO_WIEJSKA = ('0807043', 'Sulęcin', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                   'sulęciński', 'powiat')
    LUBUSKIE_SULECINSKI_TORZYM_MIEJSKO_WIEJSKA = ('0807053', 'Torzym', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                  'sulęciński', 'powiat')
    LUBUSKIE_SWIEBODZINSKI_LUBRZA_WIEJSKA = ('0808012', 'Lubrza', GminaType.WIEJSKA, 'lubuskie', 'świebodziński',
                                             'powiat')
    LUBUSKIE_SWIEBODZINSKI_LAGOW_WIEJSKA = ('0808022', 'Łagów', GminaType.WIEJSKA, 'lubuskie', 'świebodziński',
                                            'powiat')
    LUBUSKIE_SWIEBODZINSKI_SKAPE_WIEJSKA = ('0808032', 'Skąpe', GminaType.WIEJSKA, 'lubuskie', 'świebodziński',
                                            'powiat')
    LUBUSKIE_SWIEBODZINSKI_SZCZANIEC_WIEJSKA = ('0808042', 'Szczaniec', GminaType.WIEJSKA, 'lubuskie', 'świebodziński',
                                                'powiat')
    LUBUSKIE_SWIEBODZINSKI_SWIEBODZIN_MIEJSKO_WIEJSKA = ('0808053', 'Świebodzin', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                         'świebodziński', 'powiat')
    LUBUSKIE_SWIEBODZINSKI_ZBASZYNEK_MIEJSKO_WIEJSKA = ('0808063', 'Zbąszynek', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                        'świebodziński', 'powiat')
    LUBUSKIE_ZIELONOGORSKI_BABIMOST_MIEJSKO_WIEJSKA = ('0809013', 'Babimost', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                       'zielonogórski', 'powiat')
    LUBUSKIE_ZIELONOGORSKI_BOJADLA_WIEJSKA = ('0809022', 'Bojadła', GminaType.WIEJSKA, 'lubuskie', 'zielonogórski',
                                              'powiat')
    LUBUSKIE_ZIELONOGORSKI_CZERWIENSK_MIEJSKO_WIEJSKA = ('0809033', 'Czerwieńsk', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                         'zielonogórski', 'powiat')
    LUBUSKIE_ZIELONOGORSKI_KARGOWA_MIEJSKO_WIEJSKA = ('0809043', 'Kargowa', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                      'zielonogórski', 'powiat')
    LUBUSKIE_ZIELONOGORSKI_NOWOGROD_BOBRZANSKI_MIEJSKO_WIEJSKA = ('0809053', 'Nowogród Bobrzański',
                                                                  GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                                  'zielonogórski', 'powiat')
    LUBUSKIE_ZIELONOGORSKI_SULECHOW_MIEJSKO_WIEJSKA = ('0809063', 'Sulechów', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                       'zielonogórski', 'powiat')
    LUBUSKIE_ZIELONOGORSKI_SWIDNICA_WIEJSKA = ('0809072', 'Świdnica', GminaType.WIEJSKA, 'lubuskie', 'zielonogórski',
                                               'powiat')
    LUBUSKIE_ZIELONOGORSKI_TRZEBIECHOW_WIEJSKA = ('0809082', 'Trzebiechów', GminaType.WIEJSKA, 'lubuskie',
                                                  'zielonogórski', 'powiat')
    LUBUSKIE_ZIELONOGORSKI_ZABOR_WIEJSKA = ('0809092', 'Zabór', GminaType.WIEJSKA, 'lubuskie', 'zielonogórski',
                                            'powiat')
    LUBUSKIE_ZAGANSKI_GOZDNICA_MIEJSKA = ('0810011', 'Gozdnica', GminaType.MIEJSKA, 'lubuskie', 'żagański', 'powiat')
    LUBUSKIE_ZAGANSKI_ZAGAN_MIEJSKA = ('0810021', 'Żagań', GminaType.MIEJSKA, 'lubuskie', 'żagański', 'powiat')
    LUBUSKIE_ZAGANSKI_BRZEZNICA_WIEJSKA = ('0810032', 'Brzeźnica', GminaType.WIEJSKA, 'lubuskie', 'żagański', 'powiat')
    LUBUSKIE_ZAGANSKI_ILOWA_MIEJSKO_WIEJSKA = ('0810043', 'Iłowa', GminaType.MIEJSKO_WIEJSKA, 'lubuskie', 'żagański',
                                               'powiat')
    LUBUSKIE_ZAGANSKI_MALOMICE_MIEJSKO_WIEJSKA = ('0810053', 'Małomice', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                  'żagański', 'powiat')
    LUBUSKIE_ZAGANSKI_NIEGOSLAWICE_WIEJSKA = ('0810062', 'Niegosławice', GminaType.WIEJSKA, 'lubuskie', 'żagański',
                                              'powiat')
    LUBUSKIE_ZAGANSKI_SZPROTAWA_MIEJSKO_WIEJSKA = ('0810073', 'Szprotawa', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                   'żagański', 'powiat')
    LUBUSKIE_ZAGANSKI_WYMIARKI_WIEJSKA = ('0810082', 'Wymiarki', GminaType.WIEJSKA, 'lubuskie', 'żagański', 'powiat')
    LUBUSKIE_ZAGANSKI_ZAGAN_WIEJSKA = ('0810092', 'Żagań', GminaType.WIEJSKA, 'lubuskie', 'żagański', 'powiat')
    LUBUSKIE_ZARSKI_LEKNICA_MIEJSKA = ('0811011', 'Łęknica', GminaType.MIEJSKA, 'lubuskie', 'żarski', 'powiat')
    LUBUSKIE_ZARSKI_ZARY_MIEJSKA = ('0811021', 'Żary', GminaType.MIEJSKA, 'lubuskie', 'żarski', 'powiat')
    LUBUSKIE_ZARSKI_BRODY_MIEJSKO_WIEJSKA = ('0811033', 'Brody', GminaType.MIEJSKO_WIEJSKA, 'lubuskie', 'żarski',
                                             'powiat')
    LUBUSKIE_ZARSKI_JASIEN_MIEJSKO_WIEJSKA = ('0811043', 'Jasień', GminaType.MIEJSKO_WIEJSKA, 'lubuskie', 'żarski',
                                              'powiat')
    LUBUSKIE_ZARSKI_LIPINKI_LUZYCKIE_WIEJSKA = ('0811052', 'Lipinki Łużyckie', GminaType.WIEJSKA, 'lubuskie', 'żarski',
                                                'powiat')
    LUBUSKIE_ZARSKI_LUBSKO_MIEJSKO_WIEJSKA = ('0811063', 'Lubsko', GminaType.MIEJSKO_WIEJSKA, 'lubuskie', 'żarski',
                                              'powiat')
    LUBUSKIE_ZARSKI_PRZEWOZ_WIEJSKA = ('0811072', 'Przewóz', GminaType.WIEJSKA, 'lubuskie', 'żarski', 'powiat')
    LUBUSKIE_ZARSKI_TRZEBIEL_WIEJSKA = ('0811082', 'Trzebiel', GminaType.WIEJSKA, 'lubuskie', 'żarski', 'powiat')
    LUBUSKIE_ZARSKI_TUPLICE_WIEJSKA = ('0811092', 'Tuplice', GminaType.WIEJSKA, 'lubuskie', 'żarski', 'powiat')
    LUBUSKIE_ZARSKI_ZARY_WIEJSKA = ('0811102', 'Żary', GminaType.WIEJSKA, 'lubuskie', 'żarski', 'powiat')
    LUBUSKIE_WSCHOWSKI_SLAWA_MIEJSKO_WIEJSKA = ('0812013', 'Sława', GminaType.MIEJSKO_WIEJSKA, 'lubuskie', 'wschowski',
                                                'powiat')
    LUBUSKIE_WSCHOWSKI_SZLICHTYNGOWA_MIEJSKO_WIEJSKA = ('0812023', 'Szlichtyngowa', GminaType.MIEJSKO_WIEJSKA,
                                                        'lubuskie', 'wschowski', 'powiat')
    LUBUSKIE_WSCHOWSKI_WSCHOWA_MIEJSKO_WIEJSKA = ('0812033', 'Wschowa', GminaType.MIEJSKO_WIEJSKA, 'lubuskie',
                                                  'wschowski', 'powiat')
    LUBUSKIE_GORZOW_WIELKOPOLSKI_GORZOW_WIELKOPOLSKI_MIEJSKA = ('0861011', 'Gorzów Wielkopolski', GminaType.MIEJSKA,
                                                                'lubuskie', 'Gorzów Wielkopolski',
                                                                'miasto na prawach powiatu')
    LUBUSKIE_ZIELONA_GORA_ZIELONA_GORA_MIEJSKA = ('0862011', 'Zielona Góra', GminaType.MIEJSKA, 'lubuskie',
                                                  'Zielona Góra', 'miasto na prawach powiatu')

    # Łódzkie
    LODZKIE_BELCHATOWSKI_BELCHATOW_MIEJSKA = ('1001011', 'Bełchatów', GminaType.MIEJSKA, 'łódzkie', 'bełchatowski',
                                              'powiat')
    LODZKIE_BELCHATOWSKI_BELCHATOW_WIEJSKA = ('1001022', 'Bełchatów', GminaType.WIEJSKA, 'łódzkie', 'bełchatowski',
                                              'powiat')
    LODZKIE_BELCHATOWSKI_DRUZBICE_WIEJSKA = ('1001032', 'Drużbice', GminaType.WIEJSKA, 'łódzkie', 'bełchatowski',
                                             'powiat')
    LODZKIE_BELCHATOWSKI_KLESZCZOW_WIEJSKA = ('1001042', 'Kleszczów', GminaType.WIEJSKA, 'łódzkie', 'bełchatowski',
                                              'powiat')
    LODZKIE_BELCHATOWSKI_KLUKI_WIEJSKA = ('1001052', 'Kluki', GminaType.WIEJSKA, 'łódzkie', 'bełchatowski', 'powiat')
    LODZKIE_BELCHATOWSKI_RUSIEC_WIEJSKA = ('1001062', 'Rusiec', GminaType.WIEJSKA, 'łódzkie', 'bełchatowski', 'powiat')
    LODZKIE_BELCHATOWSKI_SZCZERCOW_WIEJSKA = ('1001072', 'Szczerców', GminaType.WIEJSKA, 'łódzkie', 'bełchatowski',
                                              'powiat')
    LODZKIE_BELCHATOWSKI_ZELOW_MIEJSKO_WIEJSKA = ('1001083', 'Zelów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                  'bełchatowski', 'powiat')
    LODZKIE_KUTNOWSKI_KUTNO_MIEJSKA = ('1002011', 'Kutno', GminaType.MIEJSKA, 'łódzkie', 'kutnowski', 'powiat')
    LODZKIE_KUTNOWSKI_BEDLNO_WIEJSKA = ('1002022', 'Bedlno', GminaType.WIEJSKA, 'łódzkie', 'kutnowski', 'powiat')
    LODZKIE_KUTNOWSKI_DABROWICE_MIEJSKO_WIEJSKA = ('1002033', 'Dąbrowice', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                   'kutnowski', 'powiat')
    LODZKIE_KUTNOWSKI_KROSNIEWICE_MIEJSKO_WIEJSKA = ('1002043', 'Krośniewice', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                     'kutnowski', 'powiat')
    LODZKIE_KUTNOWSKI_KRZYZANOW_WIEJSKA = ('1002052', 'Krzyżanów', GminaType.WIEJSKA, 'łódzkie', 'kutnowski', 'powiat')
    LODZKIE_KUTNOWSKI_KUTNO_WIEJSKA = ('1002062', 'Kutno', GminaType.WIEJSKA, 'łódzkie', 'kutnowski', 'powiat')
    LODZKIE_KUTNOWSKI_LANIETA_WIEJSKA = ('1002072', 'Łanięta', GminaType.WIEJSKA, 'łódzkie', 'kutnowski', 'powiat')
    LODZKIE_KUTNOWSKI_NOWE_OSTROWY_WIEJSKA = ('1002082', 'Nowe Ostrowy', GminaType.WIEJSKA, 'łódzkie', 'kutnowski',
                                              'powiat')
    LODZKIE_KUTNOWSKI_OPOROW_WIEJSKA = ('1002092', 'Oporów', GminaType.WIEJSKA, 'łódzkie', 'kutnowski', 'powiat')
    LODZKIE_KUTNOWSKI_STRZELCE_WIEJSKA = ('1002102', 'Strzelce', GminaType.WIEJSKA, 'łódzkie', 'kutnowski', 'powiat')
    LODZKIE_KUTNOWSKI_ZYCHLIN_MIEJSKO_WIEJSKA = ('1002113', 'Żychlin', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                 'kutnowski', 'powiat')
    LODZKIE_LASKI_BUCZEK_WIEJSKA = ('1003012', 'Buczek', GminaType.WIEJSKA, 'łódzkie', 'łaski', 'powiat')
    LODZKIE_LASKI_LASK_MIEJSKO_WIEJSKA = ('1003023', 'Łask', GminaType.MIEJSKO_WIEJSKA, 'łódzkie', 'łaski', 'powiat')
    LODZKIE_LASKI_SEDZIEJOWICE_WIEJSKA = ('1003032', 'Sędziejowice', GminaType.WIEJSKA, 'łódzkie', 'łaski', 'powiat')
    LODZKIE_LASKI_WIDAWA_WIEJSKA = ('1003042', 'Widawa', GminaType.WIEJSKA, 'łódzkie', 'łaski', 'powiat')
    LODZKIE_LASKI_WODZIERADY_WIEJSKA = ('1003052', 'Wodzierady', GminaType.WIEJSKA, 'łódzkie', 'łaski', 'powiat')
    LODZKIE_LECZYCKI_LECZYCA_MIEJSKA = ('1004011', 'Łęczyca', GminaType.MIEJSKA, 'łódzkie', 'łęczycki', 'powiat')
    LODZKIE_LECZYCKI_DASZYNA_WIEJSKA = ('1004022', 'Daszyna', GminaType.WIEJSKA, 'łódzkie', 'łęczycki', 'powiat')
    LODZKIE_LECZYCKI_GORA_SWIETEJ_MALGORZATY_WIEJSKA = ('1004032', 'Góra Świętej Małgorzaty', GminaType.WIEJSKA,
                                                        'łódzkie', 'łęczycki', 'powiat')
    LODZKIE_LECZYCKI_GRABOW_MIEJSKO_WIEJSKA = ('1004043', 'Grabów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie', 'łęczycki',
                                               'powiat')
    LODZKIE_LECZYCKI_LECZYCA_WIEJSKA = ('1004052', 'Łęczyca', GminaType.WIEJSKA, 'łódzkie', 'łęczycki', 'powiat')
    LODZKIE_LECZYCKI_PIATEK_MIEJSKO_WIEJSKA = ('1004063', 'Piątek', GminaType.MIEJSKO_WIEJSKA, 'łódzkie', 'łęczycki',
                                               'powiat')
    LODZKIE_LECZYCKI_SWINICE_WARCKIE_WIEJSKA = ('1004072', 'Świnice Warckie', GminaType.WIEJSKA, 'łódzkie', 'łęczycki',
                                                'powiat')
    LODZKIE_LECZYCKI_WITONIA_WIEJSKA = ('1004082', 'Witonia', GminaType.WIEJSKA, 'łódzkie', 'łęczycki', 'powiat')
    LODZKIE_LOWICKI_LOWICZ_MIEJSKA = ('1005011', 'Łowicz', GminaType.MIEJSKA, 'łódzkie', 'łowicki', 'powiat')
    LODZKIE_LOWICKI_BIELAWY_WIEJSKA = ('1005022', 'Bielawy', GminaType.WIEJSKA, 'łódzkie', 'łowicki', 'powiat')
    LODZKIE_LOWICKI_CHASNO_WIEJSKA = ('1005032', 'Chąśno', GminaType.WIEJSKA, 'łódzkie', 'łowicki', 'powiat')
    LODZKIE_LOWICKI_DOMANIEWICE_WIEJSKA = ('1005042', 'Domaniewice', GminaType.WIEJSKA, 'łódzkie', 'łowicki', 'powiat')
    LODZKIE_LOWICKI_KIERNOZIA_MIEJSKO_WIEJSKA = ('1005053', 'Kiernozia', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                 'łowicki', 'powiat')
    LODZKIE_LOWICKI_KOCIERZEW_POLUDNIOWY_WIEJSKA = ('1005062', 'Kocierzew Południowy', GminaType.WIEJSKA, 'łódzkie',
                                                    'łowicki', 'powiat')
    LODZKIE_LOWICKI_LOWICZ_WIEJSKA = ('1005072', 'Łowicz', GminaType.WIEJSKA, 'łódzkie', 'łowicki', 'powiat')
    LODZKIE_LOWICKI_LYSZKOWICE_WIEJSKA = ('1005082', 'Łyszkowice', GminaType.WIEJSKA, 'łódzkie', 'łowicki', 'powiat')
    LODZKIE_LOWICKI_NIEBOROW_WIEJSKA = ('1005092', 'Nieborów', GminaType.WIEJSKA, 'łódzkie', 'łowicki', 'powiat')
    LODZKIE_LOWICKI_ZDUNY_WIEJSKA = ('1005102', 'Zduny', GminaType.WIEJSKA, 'łódzkie', 'łowicki', 'powiat')
    LODZKIE_LODZKI_WSCHODNI_ANDRESPOL_WIEJSKA = ('1006022', 'Andrespol', GminaType.WIEJSKA, 'łódzkie',
                                                 'łódzki wschodni', 'powiat')
    LODZKIE_LODZKI_WSCHODNI_BROJCE_WIEJSKA = ('1006032', 'Brójce', GminaType.WIEJSKA, 'łódzkie', 'łódzki wschodni',
                                              'powiat')
    LODZKIE_LODZKI_WSCHODNI_KOLUSZKI_MIEJSKO_WIEJSKA = ('1006073', 'Koluszki', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                        'łódzki wschodni', 'powiat')
    LODZKIE_LODZKI_WSCHODNI_NOWOSOLNA_WIEJSKA = ('1006082', 'Nowosolna', GminaType.WIEJSKA, 'łódzkie',
                                                 'łódzki wschodni', 'powiat')
    LODZKIE_LODZKI_WSCHODNI_RZGOW_MIEJSKO_WIEJSKA = ('1006103', 'Rzgów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                     'łódzki wschodni', 'powiat')
    LODZKIE_LODZKI_WSCHODNI_TUSZYN_MIEJSKO_WIEJSKA = ('1006113', 'Tuszyn', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                      'łódzki wschodni', 'powiat')
    LODZKIE_OPOCZYNSKI_BIALACZOW_MIEJSKO_WIEJSKA = ('1007013', 'Białaczów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                    'opoczyński', 'powiat')
    LODZKIE_OPOCZYNSKI_DRZEWICA_MIEJSKO_WIEJSKA = ('1007023', 'Drzewica', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                   'opoczyński', 'powiat')
    LODZKIE_OPOCZYNSKI_MNISZKOW_WIEJSKA = ('1007032', 'Mniszków', GminaType.WIEJSKA, 'łódzkie', 'opoczyński', 'powiat')
    LODZKIE_OPOCZYNSKI_OPOCZNO_MIEJSKO_WIEJSKA = ('1007043', 'Opoczno', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                  'opoczyński', 'powiat')
    LODZKIE_OPOCZYNSKI_PARADYZ_WIEJSKA = ('1007052', 'Paradyż', GminaType.WIEJSKA, 'łódzkie', 'opoczyński', 'powiat')
    LODZKIE_OPOCZYNSKI_POSWIETNE_WIEJSKA = ('1007062', 'Poświętne', GminaType.WIEJSKA, 'łódzkie', 'opoczyński',
                                            'powiat')
    LODZKIE_OPOCZYNSKI_SLAWNO_WIEJSKA = ('1007072', 'Sławno', GminaType.WIEJSKA, 'łódzkie', 'opoczyński', 'powiat')
    LODZKIE_OPOCZYNSKI_ZARNOW_MIEJSKO_WIEJSKA = ('1007083', 'Żarnów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                 'opoczyński', 'powiat')
    LODZKIE_PABIANICKI_KONSTANTYNOW_LODZKI_MIEJSKA = ('1008011', 'Konstantynów Łódzki', GminaType.MIEJSKA, 'łódzkie',
                                                      'pabianicki', 'powiat')
    LODZKIE_PABIANICKI_PABIANICE_MIEJSKA = ('1008021', 'Pabianice', GminaType.MIEJSKA, 'łódzkie', 'pabianicki',
                                            'powiat')
    LODZKIE_PABIANICKI_DLUTOW_WIEJSKA = ('1008032', 'Dłutów', GminaType.WIEJSKA, 'łódzkie', 'pabianicki', 'powiat')
    LODZKIE_PABIANICKI_DOBRON_WIEJSKA = ('1008042', 'Dobroń', GminaType.WIEJSKA, 'łódzkie', 'pabianicki', 'powiat')
    LODZKIE_PABIANICKI_KSAWEROW_WIEJSKA = ('1008052', 'Ksawerów', GminaType.WIEJSKA, 'łódzkie', 'pabianicki', 'powiat')
    LODZKIE_PABIANICKI_LUTOMIERSK_MIEJSKO_WIEJSKA = ('1008063', 'Lutomiersk', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                     'pabianicki', 'powiat')
    LODZKIE_PABIANICKI_PABIANICE_WIEJSKA = ('1008072', 'Pabianice', GminaType.WIEJSKA, 'łódzkie', 'pabianicki',
                                            'powiat')
    LODZKIE_PAJECZANSKI_DZIALOSZYN_MIEJSKO_WIEJSKA = ('1009013', 'Działoszyn', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                      'pajęczański', 'powiat')
    LODZKIE_PAJECZANSKI_KIELCZYGLOW_WIEJSKA = ('1009022', 'Kiełczygłów', GminaType.WIEJSKA, 'łódzkie', 'pajęczański',
                                               'powiat')
    LODZKIE_PAJECZANSKI_NOWA_BRZEZNICA_WIEJSKA = ('1009032', 'Nowa Brzeźnica', GminaType.WIEJSKA, 'łódzkie',
                                                  'pajęczański', 'powiat')
    LODZKIE_PAJECZANSKI_PAJECZNO_MIEJSKO_WIEJSKA = ('1009043', 'Pajęczno', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                    'pajęczański', 'powiat')
    LODZKIE_PAJECZANSKI_RZASNIA_WIEJSKA = ('1009052', 'Rząśnia', GminaType.WIEJSKA, 'łódzkie', 'pajęczański', 'powiat')
    LODZKIE_PAJECZANSKI_SIEMKOWICE_WIEJSKA = ('1009062', 'Siemkowice', GminaType.WIEJSKA, 'łódzkie', 'pajęczański',
                                              'powiat')
    LODZKIE_PAJECZANSKI_STRZELCE_WIELKIE_WIEJSKA = ('1009072', 'Strzelce Wielkie', GminaType.WIEJSKA, 'łódzkie',
                                                    'pajęczański', 'powiat')
    LODZKIE_PAJECZANSKI_SULMIERZYCE_WIEJSKA = ('1009082', 'Sulmierzyce', GminaType.WIEJSKA, 'łódzkie', 'pajęczański',
                                               'powiat')
    LODZKIE_PIOTRKOWSKI_ALEKSANDROW_WIEJSKA = ('1010012', 'Aleksandrów', GminaType.WIEJSKA, 'łódzkie', 'piotrkowski',
                                               'powiat')
    LODZKIE_PIOTRKOWSKI_CZARNOCIN_WIEJSKA = ('1010022', 'Czarnocin', GminaType.WIEJSKA, 'łódzkie', 'piotrkowski',
                                             'powiat')
    LODZKIE_PIOTRKOWSKI_GORZKOWICE_WIEJSKA = ('1010032', 'Gorzkowice', GminaType.WIEJSKA, 'łódzkie', 'piotrkowski',
                                              'powiat')
    LODZKIE_PIOTRKOWSKI_GRABICA_WIEJSKA = ('1010042', 'Grabica', GminaType.WIEJSKA, 'łódzkie', 'piotrkowski', 'powiat')
    LODZKIE_PIOTRKOWSKI_LEKI_SZLACHECKIE_WIEJSKA = ('1010052', 'Łęki Szlacheckie', GminaType.WIEJSKA, 'łódzkie',
                                                    'piotrkowski', 'powiat')
    LODZKIE_PIOTRKOWSKI_MOSZCZENICA_WIEJSKA = ('1010062', 'Moszczenica', GminaType.WIEJSKA, 'łódzkie', 'piotrkowski',
                                               'powiat')
    LODZKIE_PIOTRKOWSKI_RECZNO_WIEJSKA = ('1010072', 'Ręczno', GminaType.WIEJSKA, 'łódzkie', 'piotrkowski', 'powiat')
    LODZKIE_PIOTRKOWSKI_ROZPRZA_MIEJSKO_WIEJSKA = ('1010083', 'Rozprza', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                   'piotrkowski', 'powiat')
    LODZKIE_PIOTRKOWSKI_SULEJOW_MIEJSKO_WIEJSKA = ('1010093', 'Sulejów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                   'piotrkowski', 'powiat')
    LODZKIE_PIOTRKOWSKI_WOLA_KRZYSZTOPORSKA_WIEJSKA = ('1010102', 'Wola Krzysztoporska', GminaType.WIEJSKA, 'łódzkie',
                                                       'piotrkowski', 'powiat')
    LODZKIE_PIOTRKOWSKI_WOLBORZ_MIEJSKO_WIEJSKA = ('1010113', 'Wolbórz', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                   'piotrkowski', 'powiat')
    LODZKIE_PODDEBICKI_DALIKOW_WIEJSKA = ('1011012', 'Dalików', GminaType.WIEJSKA, 'łódzkie', 'poddębicki', 'powiat')
    LODZKIE_PODDEBICKI_PECZNIEW_WIEJSKA = ('1011022', 'Pęczniew', GminaType.WIEJSKA, 'łódzkie', 'poddębicki', 'powiat')
    LODZKIE_PODDEBICKI_PODDEBICE_MIEJSKO_WIEJSKA = ('1011033', 'Poddębice', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                    'poddębicki', 'powiat')
    LODZKIE_PODDEBICKI_UNIEJOW_MIEJSKO_WIEJSKA = ('1011043', 'Uniejów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                  'poddębicki', 'powiat')
    LODZKIE_PODDEBICKI_WARTKOWICE_WIEJSKA = ('1011052', 'Wartkowice', GminaType.WIEJSKA, 'łódzkie', 'poddębicki',
                                             'powiat')
    LODZKIE_PODDEBICKI_ZADZIM_WIEJSKA = ('1011062', 'Zadzim', GminaType.WIEJSKA, 'łódzkie', 'poddębicki', 'powiat')
    LODZKIE_RADOMSZCZANSKI_RADOMSKO_MIEJSKA = ('1012011', 'Radomsko', GminaType.MIEJSKA, 'łódzkie', 'radomszczański',
                                               'powiat')
    LODZKIE_RADOMSZCZANSKI_DOBRYSZYCE_WIEJSKA = ('1012022', 'Dobryszyce', GminaType.WIEJSKA, 'łódzkie',
                                                 'radomszczański', 'powiat')
    LODZKIE_RADOMSZCZANSKI_GIDLE_WIEJSKA = ('1012032', 'Gidle', GminaType.WIEJSKA, 'łódzkie', 'radomszczański',
                                            'powiat')
    LODZKIE_RADOMSZCZANSKI_GOMUNICE_WIEJSKA = ('1012042', 'Gomunice', GminaType.WIEJSKA, 'łódzkie', 'radomszczański',
                                               'powiat')
    LODZKIE_RADOMSZCZANSKI_KAMIENSK_MIEJSKO_WIEJSKA = ('1012053', 'Kamieńsk', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                       'radomszczański', 'powiat')
    LODZKIE_RADOMSZCZANSKI_KOBIELE_WIELKIE_WIEJSKA = ('1012062', 'Kobiele Wielkie', GminaType.WIEJSKA, 'łódzkie',
                                                      'radomszczański', 'powiat')
    LODZKIE_RADOMSZCZANSKI_KODRAB_WIEJSKA = ('1012072', 'Kodrąb', GminaType.WIEJSKA, 'łódzkie', 'radomszczański',
                                             'powiat')
    LODZKIE_RADOMSZCZANSKI_LGOTA_WIELKA_WIEJSKA = ('1012082', 'Lgota Wielka', GminaType.WIEJSKA, 'łódzkie',
                                                   'radomszczański', 'powiat')
    LODZKIE_RADOMSZCZANSKI_LADZICE_WIEJSKA = ('1012092', 'Ładzice', GminaType.WIEJSKA, 'łódzkie', 'radomszczański',
                                              'powiat')
    LODZKIE_RADOMSZCZANSKI_MASLOWICE_WIEJSKA = ('1012102', 'Masłowice', GminaType.WIEJSKA, 'łódzkie', 'radomszczański',
                                                'powiat')
    LODZKIE_RADOMSZCZANSKI_PRZEDBORZ_MIEJSKO_WIEJSKA = ('1012113', 'Przedbórz', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                        'radomszczański', 'powiat')
    LODZKIE_RADOMSZCZANSKI_RADOMSKO_WIEJSKA = ('1012122', 'Radomsko', GminaType.WIEJSKA, 'łódzkie', 'radomszczański',
                                               'powiat')
    LODZKIE_RADOMSZCZANSKI_WIELGOMLYNY_WIEJSKA = ('1012132', 'Wielgomłyny', GminaType.WIEJSKA, 'łódzkie',
                                                  'radomszczański', 'powiat')
    LODZKIE_RADOMSZCZANSKI_ZYTNO_WIEJSKA = ('1012142', 'Żytno', GminaType.WIEJSKA, 'łódzkie', 'radomszczański',
                                            'powiat')
    LODZKIE_RAWSKI_RAWA_MAZOWIECKA_MIEJSKA = ('1013011', 'Rawa Mazowiecka', GminaType.MIEJSKA, 'łódzkie', 'rawski',
                                              'powiat')
    LODZKIE_RAWSKI_BIALA_RAWSKA_MIEJSKO_WIEJSKA = ('1013023', 'Biała Rawska', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                   'rawski', 'powiat')
    LODZKIE_RAWSKI_CIELADZ_WIEJSKA = ('1013032', 'Cielądz', GminaType.WIEJSKA, 'łódzkie', 'rawski', 'powiat')
    LODZKIE_RAWSKI_RAWA_MAZOWIECKA_WIEJSKA = ('1013042', 'Rawa Mazowiecka', GminaType.WIEJSKA, 'łódzkie', 'rawski',
                                              'powiat')
    LODZKIE_RAWSKI_REGNOW_WIEJSKA = ('1013052', 'Regnów', GminaType.WIEJSKA, 'łódzkie', 'rawski', 'powiat')
    LODZKIE_RAWSKI_SADKOWICE_WIEJSKA = ('1013062', 'Sadkowice', GminaType.WIEJSKA, 'łódzkie', 'rawski', 'powiat')
    LODZKIE_SIERADZKI_SIERADZ_MIEJSKA = ('1014011', 'Sieradz', GminaType.MIEJSKA, 'łódzkie', 'sieradzki', 'powiat')
    LODZKIE_SIERADZKI_BLASZKI_MIEJSKO_WIEJSKA = ('1014023', 'Błaszki', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                 'sieradzki', 'powiat')
    LODZKIE_SIERADZKI_BRASZEWICE_WIEJSKA = ('1014032', 'Brąszewice', GminaType.WIEJSKA, 'łódzkie', 'sieradzki',
                                            'powiat')
    LODZKIE_SIERADZKI_BRZEZNIO_WIEJSKA = ('1014042', 'Brzeźnio', GminaType.WIEJSKA, 'łódzkie', 'sieradzki', 'powiat')
    LODZKIE_SIERADZKI_BURZENIN_WIEJSKA = ('1014052', 'Burzenin', GminaType.WIEJSKA, 'łódzkie', 'sieradzki', 'powiat')
    LODZKIE_SIERADZKI_GOSZCZANOW_WIEJSKA = ('1014062', 'Goszczanów', GminaType.WIEJSKA, 'łódzkie', 'sieradzki',
                                            'powiat')
    LODZKIE_SIERADZKI_KLONOWA_WIEJSKA = ('1014072', 'Klonowa', GminaType.WIEJSKA, 'łódzkie', 'sieradzki', 'powiat')
    LODZKIE_SIERADZKI_SIERADZ_WIEJSKA = ('1014082', 'Sieradz', GminaType.WIEJSKA, 'łódzkie', 'sieradzki', 'powiat')
    LODZKIE_SIERADZKI_WARTA_MIEJSKO_WIEJSKA = ('1014093', 'Warta', GminaType.MIEJSKO_WIEJSKA, 'łódzkie', 'sieradzki',
                                               'powiat')
    LODZKIE_SIERADZKI_WROBLEW_WIEJSKA = ('1014102', 'Wróblew', GminaType.WIEJSKA, 'łódzkie', 'sieradzki', 'powiat')
    LODZKIE_SIERADZKI_ZLOCZEW_MIEJSKO_WIEJSKA = ('1014113', 'Złoczew', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                 'sieradzki', 'powiat')
    LODZKIE_SKIERNIEWICKI_BOLIMOW_MIEJSKO_WIEJSKA = ('1015013', 'Bolimów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                     'skierniewicki', 'powiat')
    LODZKIE_SKIERNIEWICKI_GLUCHOW_WIEJSKA = ('1015022', 'Głuchów', GminaType.WIEJSKA, 'łódzkie', 'skierniewicki',
                                             'powiat')
    LODZKIE_SKIERNIEWICKI_GODZIANOW_WIEJSKA = ('1015032', 'Godzianów', GminaType.WIEJSKA, 'łódzkie', 'skierniewicki',
                                               'powiat')
    LODZKIE_SKIERNIEWICKI_KOWIESY_WIEJSKA = ('1015042', 'Kowiesy', GminaType.WIEJSKA, 'łódzkie', 'skierniewicki',
                                             'powiat')
    LODZKIE_SKIERNIEWICKI_LIPCE_REYMONTOWSKIE_WIEJSKA = ('1015052', 'Lipce Reymontowskie', GminaType.WIEJSKA, 'łódzkie',
                                                         'skierniewicki', 'powiat')
    LODZKIE_SKIERNIEWICKI_MAKOW_WIEJSKA = ('1015062', 'Maków', GminaType.WIEJSKA, 'łódzkie', 'skierniewicki', 'powiat')
    LODZKIE_SKIERNIEWICKI_NOWY_KAWECZYN_WIEJSKA = ('1015072', 'Nowy Kawęczyn', GminaType.WIEJSKA, 'łódzkie',
                                                   'skierniewicki', 'powiat')
    LODZKIE_SKIERNIEWICKI_SKIERNIEWICE_WIEJSKA = ('1015082', 'Skierniewice', GminaType.WIEJSKA, 'łódzkie',
                                                  'skierniewicki', 'powiat')
    LODZKIE_SKIERNIEWICKI_SLUPIA_WIEJSKA = ('1015092', 'Słupia', GminaType.WIEJSKA, 'łódzkie', 'skierniewicki',
                                            'powiat')
    LODZKIE_TOMASZOWSKI_TOMASZOW_MAZOWIECKI_MIEJSKA = ('1016011', 'Tomaszów Mazowiecki', GminaType.MIEJSKA, 'łódzkie',
                                                       'tomaszowski', 'powiat')
    LODZKIE_TOMASZOWSKI_BEDKOW_WIEJSKA = ('1016022', 'Będków', GminaType.WIEJSKA, 'łódzkie', 'tomaszowski', 'powiat')
    LODZKIE_TOMASZOWSKI_BUDZISZEWICE_WIEJSKA = ('1016032', 'Budziszewice', GminaType.WIEJSKA, 'łódzkie', 'tomaszowski',
                                                'powiat')
    LODZKIE_TOMASZOWSKI_CZERNIEWICE_WIEJSKA = ('1016042', 'Czerniewice', GminaType.WIEJSKA, 'łódzkie', 'tomaszowski',
                                               'powiat')
    LODZKIE_TOMASZOWSKI_INOWLODZ_MIEJSKO_WIEJSKA = ('1016053', 'Inowłódz', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                    'tomaszowski', 'powiat')
    LODZKIE_TOMASZOWSKI_LUBOCHNIA_WIEJSKA = ('1016062', 'Lubochnia', GminaType.WIEJSKA, 'łódzkie', 'tomaszowski',
                                             'powiat')
    LODZKIE_TOMASZOWSKI_ROKICINY_WIEJSKA = ('1016072', 'Rokiciny', GminaType.WIEJSKA, 'łódzkie', 'tomaszowski',
                                            'powiat')
    LODZKIE_TOMASZOWSKI_RZECZYCA_WIEJSKA = ('1016082', 'Rzeczyca', GminaType.WIEJSKA, 'łódzkie', 'tomaszowski',
                                            'powiat')
    LODZKIE_TOMASZOWSKI_TOMASZOW_MAZOWIECKI_WIEJSKA = ('1016092', 'Tomaszów Mazowiecki', GminaType.WIEJSKA, 'łódzkie',
                                                       'tomaszowski', 'powiat')
    LODZKIE_TOMASZOWSKI_UJAZD_MIEJSKO_WIEJSKA = ('1016103', 'Ujazd', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                 'tomaszowski', 'powiat')
    LODZKIE_TOMASZOWSKI_ZELECHLINEK_WIEJSKA = ('1016112', 'Żelechlinek', GminaType.WIEJSKA, 'łódzkie', 'tomaszowski',
                                               'powiat')
    LODZKIE_WIELUNSKI_BIALA_WIEJSKA = ('1017012', 'Biała', GminaType.WIEJSKA, 'łódzkie', 'wieluński', 'powiat')
    LODZKIE_WIELUNSKI_CZARNOZYLY_WIEJSKA = ('1017022', 'Czarnożyły', GminaType.WIEJSKA, 'łódzkie', 'wieluński',
                                            'powiat')
    LODZKIE_WIELUNSKI_KONOPNICA_WIEJSKA = ('1017032', 'Konopnica', GminaType.WIEJSKA, 'łódzkie', 'wieluński', 'powiat')
    LODZKIE_WIELUNSKI_MOKRSKO_WIEJSKA = ('1017042', 'Mokrsko', GminaType.WIEJSKA, 'łódzkie', 'wieluński', 'powiat')
    LODZKIE_WIELUNSKI_OSJAKOW_MIEJSKO_WIEJSKA = ('1017053', 'Osjaków', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                 'wieluński', 'powiat')
    LODZKIE_WIELUNSKI_OSTROWEK_WIEJSKA = ('1017062', 'Ostrówek', GminaType.WIEJSKA, 'łódzkie', 'wieluński', 'powiat')
    LODZKIE_WIELUNSKI_PATNOW_WIEJSKA = ('1017072', 'Pątnów', GminaType.WIEJSKA, 'łódzkie', 'wieluński', 'powiat')
    LODZKIE_WIELUNSKI_SKOMLIN_WIEJSKA = ('1017082', 'Skomlin', GminaType.WIEJSKA, 'łódzkie', 'wieluński', 'powiat')
    LODZKIE_WIELUNSKI_WIELUN_MIEJSKO_WIEJSKA = ('1017093', 'Wieluń', GminaType.MIEJSKO_WIEJSKA, 'łódzkie', 'wieluński',
                                                'powiat')
    LODZKIE_WIELUNSKI_WIERZCHLAS_WIEJSKA = ('1017102', 'Wierzchlas', GminaType.WIEJSKA, 'łódzkie', 'wieluński',
                                            'powiat')
    LODZKIE_WIERUSZOWSKI_BOLESLAWIEC_MIEJSKO_WIEJSKA = ('1018013', 'Bolesławiec', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                        'wieruszowski', 'powiat')
    LODZKIE_WIERUSZOWSKI_CZASTARY_WIEJSKA = ('1018022', 'Czastary', GminaType.WIEJSKA, 'łódzkie', 'wieruszowski',
                                             'powiat')
    LODZKIE_WIERUSZOWSKI_GALEWICE_WIEJSKA = ('1018032', 'Galewice', GminaType.WIEJSKA, 'łódzkie', 'wieruszowski',
                                             'powiat')
    LODZKIE_WIERUSZOWSKI_LUTUTOW_MIEJSKO_WIEJSKA = ('1018043', 'Lututów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                    'wieruszowski', 'powiat')
    LODZKIE_WIERUSZOWSKI_LUBNICE_WIEJSKA = ('1018052', 'Łubnice', GminaType.WIEJSKA, 'łódzkie', 'wieruszowski',
                                            'powiat')
    LODZKIE_WIERUSZOWSKI_SOKOLNIKI_WIEJSKA = ('1018062', 'Sokolniki', GminaType.WIEJSKA, 'łódzkie', 'wieruszowski',
                                              'powiat')
    LODZKIE_WIERUSZOWSKI_WIERUSZOW_MIEJSKO_WIEJSKA = ('1018073', 'Wieruszów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                      'wieruszowski', 'powiat')
    LODZKIE_ZDUNSKOWOLSKI_ZDUNSKA_WOLA_MIEJSKA = ('1019011', 'Zduńska Wola', GminaType.MIEJSKA, 'łódzkie',
                                                  'zduńskowolski', 'powiat')
    LODZKIE_ZDUNSKOWOLSKI_SZADEK_MIEJSKO_WIEJSKA = ('1019023', 'Szadek', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                    'zduńskowolski', 'powiat')
    LODZKIE_ZDUNSKOWOLSKI_ZAPOLICE_WIEJSKA = ('1019032', 'Zapolice', GminaType.WIEJSKA, 'łódzkie', 'zduńskowolski',
                                              'powiat')
    LODZKIE_ZDUNSKOWOLSKI_ZDUNSKA_WOLA_WIEJSKA = ('1019042', 'Zduńska Wola', GminaType.WIEJSKA, 'łódzkie',
                                                  'zduńskowolski', 'powiat')
    LODZKIE_ZGIERSKI_GLOWNO_MIEJSKA = ('1020011', 'Głowno', GminaType.MIEJSKA, 'łódzkie', 'zgierski', 'powiat')
    LODZKIE_ZGIERSKI_OZORKOW_MIEJSKA = ('1020021', 'Ozorków', GminaType.MIEJSKA, 'łódzkie', 'zgierski', 'powiat')
    LODZKIE_ZGIERSKI_ZGIERZ_MIEJSKA = ('1020031', 'Zgierz', GminaType.MIEJSKA, 'łódzkie', 'zgierski', 'powiat')
    LODZKIE_ZGIERSKI_ALEKSANDROW_LODZKI_MIEJSKO_WIEJSKA = ('1020043', 'Aleksandrów Łódzki', GminaType.MIEJSKO_WIEJSKA,
                                                           'łódzkie', 'zgierski', 'powiat')
    LODZKIE_ZGIERSKI_GLOWNO_WIEJSKA = ('1020052', 'Głowno', GminaType.WIEJSKA, 'łódzkie', 'zgierski', 'powiat')
    LODZKIE_ZGIERSKI_OZORKOW_WIEJSKA = ('1020062', 'Ozorków', GminaType.WIEJSKA, 'łódzkie', 'zgierski', 'powiat')
    LODZKIE_ZGIERSKI_PARZECZEW_MIEJSKO_WIEJSKA = ('1020073', 'Parzęczew', GminaType.MIEJSKO_WIEJSKA, 'łódzkie',
                                                  'zgierski', 'powiat')
    LODZKIE_ZGIERSKI_STRYKOW_MIEJSKO_WIEJSKA = ('1020083', 'Stryków', GminaType.MIEJSKO_WIEJSKA, 'łódzkie', 'zgierski',
                                                'powiat')
    LODZKIE_ZGIERSKI_ZGIERZ_WIEJSKA = ('1020092', 'Zgierz', GminaType.WIEJSKA, 'łódzkie', 'zgierski', 'powiat')
    LODZKIE_BRZEZINSKI_BRZEZINY_MIEJSKA = ('1021011', 'Brzeziny', GminaType.MIEJSKA, 'łódzkie', 'brzeziński', 'powiat')
    LODZKIE_BRZEZINSKI_BRZEZINY_WIEJSKA = ('1021022', 'Brzeziny', GminaType.WIEJSKA, 'łódzkie', 'brzeziński', 'powiat')
    LODZKIE_BRZEZINSKI_DMOSIN_WIEJSKA = ('1021032', 'Dmosin', GminaType.WIEJSKA, 'łódzkie', 'brzeziński', 'powiat')
    LODZKIE_BRZEZINSKI_JEZOW_MIEJSKO_WIEJSKA = ('1021043', 'Jeżów', GminaType.MIEJSKO_WIEJSKA, 'łódzkie', 'brzeziński',
                                                'powiat')
    LODZKIE_BRZEZINSKI_ROGOW_WIEJSKA = ('1021052', 'Rogów', GminaType.WIEJSKA, 'łódzkie', 'brzeziński', 'powiat')
    LODZKIE_LODZ_LODZ_MIEJSKA = ('1061011', 'Łódź', GminaType.MIEJSKA, 'łódzkie', 'Łódź', 'miasto na prawach powiatu')
    LODZKIE_PIOTRKOW_TRYBUNALSKI_PIOTRKOW_TRYBUNALSKI_MIEJSKA = ('1062011', 'Piotrków Trybunalski', GminaType.MIEJSKA,
                                                                 'łódzkie', 'Piotrków Trybunalski',
                                                                 'miasto na prawach powiatu')
    LODZKIE_SKIERNIEWICE_SKIERNIEWICE_MIEJSKA = ('1063011', 'Skierniewice', GminaType.MIEJSKA, 'łódzkie',
                                                 'Skierniewice', 'miasto na prawach powiatu')

    # Małopolskie
    MALOPOLSKIE_BOCHENSKI_BOCHNIA_MIEJSKA = ('1201011', 'Bochnia', GminaType.MIEJSKA, 'małopolskie', 'bocheński',
                                             'powiat')
    MALOPOLSKIE_BOCHENSKI_BOCHNIA_WIEJSKA = ('1201022', 'Bochnia', GminaType.WIEJSKA, 'małopolskie', 'bocheński',
                                             'powiat')
    MALOPOLSKIE_BOCHENSKI_DRWINIA_WIEJSKA = ('1201032', 'Drwinia', GminaType.WIEJSKA, 'małopolskie', 'bocheński',
                                             'powiat')
    MALOPOLSKIE_BOCHENSKI_LIPNICA_MUROWANA_WIEJSKA = ('1201042', 'Lipnica Murowana', GminaType.WIEJSKA, 'małopolskie',
                                                      'bocheński', 'powiat')
    MALOPOLSKIE_BOCHENSKI_LAPANOW_WIEJSKA = ('1201052', 'Łapanów', GminaType.WIEJSKA, 'małopolskie', 'bocheński',
                                             'powiat')
    MALOPOLSKIE_BOCHENSKI_NOWY_WISNICZ_MIEJSKO_WIEJSKA = ('1201063', 'Nowy Wiśnicz', GminaType.MIEJSKO_WIEJSKA,
                                                          'małopolskie', 'bocheński', 'powiat')
    MALOPOLSKIE_BOCHENSKI_RZEZAWA_WIEJSKA = ('1201072', 'Rzezawa', GminaType.WIEJSKA, 'małopolskie', 'bocheński',
                                             'powiat')
    MALOPOLSKIE_BOCHENSKI_TRZCIANA_WIEJSKA = ('1201082', 'Trzciana', GminaType.WIEJSKA, 'małopolskie', 'bocheński',
                                              'powiat')
    MALOPOLSKIE_BOCHENSKI_ZEGOCINA_WIEJSKA = ('1201092', 'Żegocina', GminaType.WIEJSKA, 'małopolskie', 'bocheński',
                                              'powiat')
    MALOPOLSKIE_BRZESKI_BORZECIN_WIEJSKA = ('1202012', 'Borzęcin', GminaType.WIEJSKA, 'małopolskie', 'brzeski',
                                            'powiat')
    MALOPOLSKIE_BRZESKI_BRZESKO_MIEJSKO_WIEJSKA = ('1202023', 'Brzesko', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                   'brzeski', 'powiat')
    MALOPOLSKIE_BRZESKI_CZCHOW_MIEJSKO_WIEJSKA = ('1202033', 'Czchów', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                  'brzeski', 'powiat')
    MALOPOLSKIE_BRZESKI_DEBNO_WIEJSKA = ('1202042', 'Dębno', GminaType.WIEJSKA, 'małopolskie', 'brzeski', 'powiat')
    MALOPOLSKIE_BRZESKI_GNOJNIK_WIEJSKA = ('1202052', 'Gnojnik', GminaType.WIEJSKA, 'małopolskie', 'brzeski', 'powiat')
    MALOPOLSKIE_BRZESKI_IWKOWA_WIEJSKA = ('1202062', 'Iwkowa', GminaType.WIEJSKA, 'małopolskie', 'brzeski', 'powiat')
    MALOPOLSKIE_BRZESKI_SZCZUROWA_WIEJSKA = ('1202072', 'Szczurowa', GminaType.WIEJSKA, 'małopolskie', 'brzeski',
                                             'powiat')
    MALOPOLSKIE_CHRZANOWSKI_ALWERNIA_MIEJSKO_WIEJSKA = ('1203013', 'Alwernia', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                        'chrzanowski', 'powiat')
    MALOPOLSKIE_CHRZANOWSKI_BABICE_WIEJSKA = ('1203022', 'Babice', GminaType.WIEJSKA, 'małopolskie', 'chrzanowski',
                                              'powiat')
    MALOPOLSKIE_CHRZANOWSKI_CHRZANOW_MIEJSKO_WIEJSKA = ('1203033', 'Chrzanów', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                        'chrzanowski', 'powiat')
    MALOPOLSKIE_CHRZANOWSKI_LIBIAZ_MIEJSKO_WIEJSKA = ('1203043', 'Libiąż', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                      'chrzanowski', 'powiat')
    MALOPOLSKIE_CHRZANOWSKI_TRZEBINIA_MIEJSKO_WIEJSKA = ('1203053', 'Trzebinia', GminaType.MIEJSKO_WIEJSKA,
                                                         'małopolskie', 'chrzanowski', 'powiat')
    MALOPOLSKIE_DABROWSKI_BOLESLAW_WIEJSKA = ('1204012', 'Bolesław', GminaType.WIEJSKA, 'małopolskie', 'dąbrowski',
                                              'powiat')
    MALOPOLSKIE_DABROWSKI_DABROWA_TARNOWSKA_MIEJSKO_WIEJSKA = ('1204023', 'Dąbrowa Tarnowska',
                                                               GminaType.MIEJSKO_WIEJSKA, 'małopolskie', 'dąbrowski',
                                                               'powiat')
    MALOPOLSKIE_DABROWSKI_GREBOSZOW_WIEJSKA = ('1204032', 'Gręboszów', GminaType.WIEJSKA, 'małopolskie', 'dąbrowski',
                                               'powiat')
    MALOPOLSKIE_DABROWSKI_MEDRZECHOW_WIEJSKA = ('1204042', 'Mędrzechów', GminaType.WIEJSKA, 'małopolskie', 'dąbrowski',
                                                'powiat')
    MALOPOLSKIE_DABROWSKI_OLESNO_WIEJSKA = ('1204052', 'Olesno', GminaType.WIEJSKA, 'małopolskie', 'dąbrowski',
                                            'powiat')
    MALOPOLSKIE_DABROWSKI_RADGOSZCZ_WIEJSKA = ('1204062', 'Radgoszcz', GminaType.WIEJSKA, 'małopolskie', 'dąbrowski',
                                               'powiat')
    MALOPOLSKIE_DABROWSKI_SZCZUCIN_MIEJSKO_WIEJSKA = ('1204073', 'Szczucin', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                      'dąbrowski', 'powiat')
    MALOPOLSKIE_GORLICKI_GORLICE_MIEJSKA = ('1205011', 'Gorlice', GminaType.MIEJSKA, 'małopolskie', 'gorlicki',
                                            'powiat')
    MALOPOLSKIE_GORLICKI_BIECZ_MIEJSKO_WIEJSKA = ('1205023', 'Biecz', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                  'gorlicki', 'powiat')
    MALOPOLSKIE_GORLICKI_BOBOWA_MIEJSKO_WIEJSKA = ('1205033', 'Bobowa', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                   'gorlicki', 'powiat')
    MALOPOLSKIE_GORLICKI_GORLICE_WIEJSKA = ('1205042', 'Gorlice', GminaType.WIEJSKA, 'małopolskie', 'gorlicki',
                                            'powiat')
    MALOPOLSKIE_GORLICKI_LIPINKI_WIEJSKA = ('1205052', 'Lipinki', GminaType.WIEJSKA, 'małopolskie', 'gorlicki',
                                            'powiat')
    MALOPOLSKIE_GORLICKI_LUZNA_WIEJSKA = ('1205062', 'Łużna', GminaType.WIEJSKA, 'małopolskie', 'gorlicki', 'powiat')
    MALOPOLSKIE_GORLICKI_MOSZCZENICA_WIEJSKA = ('1205072', 'Moszczenica', GminaType.WIEJSKA, 'małopolskie', 'gorlicki',
                                                'powiat')
    MALOPOLSKIE_GORLICKI_ROPA_WIEJSKA = ('1205082', 'Ropa', GminaType.WIEJSKA, 'małopolskie', 'gorlicki', 'powiat')
    MALOPOLSKIE_GORLICKI_SEKOWA_WIEJSKA = ('1205092', 'Sękowa', GminaType.WIEJSKA, 'małopolskie', 'gorlicki', 'powiat')
    MALOPOLSKIE_GORLICKI_USCIE_GORLICKIE_WIEJSKA = ('1205102', 'Uście Gorlickie', GminaType.WIEJSKA, 'małopolskie',
                                                    'gorlicki', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_CZERNICHOW_WIEJSKA = ('1206012', 'Czernichów', GminaType.WIEJSKA, 'małopolskie', 'krakowski',
                                                'powiat')
    MALOPOLSKIE_KRAKOWSKI_IGOLOMIA_WAWRZENCZYCE_WIEJSKA = ('1206022', 'Igołomia-Wawrzeńczyce', GminaType.WIEJSKA,
                                                           'małopolskie', 'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_IWANOWICE_WIEJSKA = ('1206032', 'Iwanowice', GminaType.WIEJSKA, 'małopolskie', 'krakowski',
                                               'powiat')
    MALOPOLSKIE_KRAKOWSKI_JERZMANOWICE_PRZEGINIA_WIEJSKA = ('1206042', 'Jerzmanowice-Przeginia', GminaType.WIEJSKA,
                                                            'małopolskie', 'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_KOCMYRZOW_LUBORZYCA_WIEJSKA = ('1206052', 'Kocmyrzów-Luborzyca', GminaType.WIEJSKA,
                                                         'małopolskie', 'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_KRZESZOWICE_MIEJSKO_WIEJSKA = ('1206063', 'Krzeszowice', GminaType.MIEJSKO_WIEJSKA,
                                                         'małopolskie', 'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_LISZKI_WIEJSKA = ('1206072', 'Liszki', GminaType.WIEJSKA, 'małopolskie', 'krakowski',
                                            'powiat')
    MALOPOLSKIE_KRAKOWSKI_MICHALOWICE_WIEJSKA = ('1206082', 'Michałowice', GminaType.WIEJSKA, 'małopolskie',
                                                 'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_MOGILANY_WIEJSKA = ('1206092', 'Mogilany', GminaType.WIEJSKA, 'małopolskie', 'krakowski',
                                              'powiat')
    MALOPOLSKIE_KRAKOWSKI_SKALA_MIEJSKO_WIEJSKA = ('1206103', 'Skała', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                   'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_SKAWINA_MIEJSKO_WIEJSKA = ('1206113', 'Skawina', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                     'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_SLOMNIKI_MIEJSKO_WIEJSKA = ('1206123', 'Słomniki', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                      'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_SULOSZOWA_WIEJSKA = ('1206132', 'Sułoszowa', GminaType.WIEJSKA, 'małopolskie', 'krakowski',
                                               'powiat')
    MALOPOLSKIE_KRAKOWSKI_SWIATNIKI_GORNE_MIEJSKO_WIEJSKA = ('1206143', 'Świątniki Górne', GminaType.MIEJSKO_WIEJSKA,
                                                             'małopolskie', 'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_WIELKA_WIES_WIEJSKA = ('1206152', 'Wielka Wieś', GminaType.WIEJSKA, 'małopolskie',
                                                 'krakowski', 'powiat')
    MALOPOLSKIE_KRAKOWSKI_ZABIERZOW_WIEJSKA = ('1206162', 'Zabierzów', GminaType.WIEJSKA, 'małopolskie', 'krakowski',
                                               'powiat')
    MALOPOLSKIE_KRAKOWSKI_ZIELONKI_WIEJSKA = ('1206172', 'Zielonki', GminaType.WIEJSKA, 'małopolskie', 'krakowski',
                                              'powiat')
    MALOPOLSKIE_LIMANOWSKI_LIMANOWA_MIEJSKA = ('1207011', 'Limanowa', GminaType.MIEJSKA, 'małopolskie', 'limanowski',
                                               'powiat')
    MALOPOLSKIE_LIMANOWSKI_MSZANA_DOLNA_MIEJSKA = ('1207021', 'Mszana Dolna', GminaType.MIEJSKA, 'małopolskie',
                                                   'limanowski', 'powiat')
    MALOPOLSKIE_LIMANOWSKI_DOBRA_WIEJSKA = ('1207032', 'Dobra', GminaType.WIEJSKA, 'małopolskie', 'limanowski',
                                            'powiat')
    MALOPOLSKIE_LIMANOWSKI_JODLOWNIK_WIEJSKA = ('1207042', 'Jodłownik', GminaType.WIEJSKA, 'małopolskie', 'limanowski',
                                                'powiat')
    MALOPOLSKIE_LIMANOWSKI_KAMIENICA_WIEJSKA = ('1207052', 'Kamienica', GminaType.WIEJSKA, 'małopolskie', 'limanowski',
                                                'powiat')
    MALOPOLSKIE_LIMANOWSKI_LASKOWA_WIEJSKA = ('1207062', 'Laskowa', GminaType.WIEJSKA, 'małopolskie', 'limanowski',
                                              'powiat')
    MALOPOLSKIE_LIMANOWSKI_LIMANOWA_WIEJSKA = ('1207072', 'Limanowa', GminaType.WIEJSKA, 'małopolskie', 'limanowski',
                                               'powiat')
    MALOPOLSKIE_LIMANOWSKI_LUKOWICA_WIEJSKA = ('1207082', 'Łukowica', GminaType.WIEJSKA, 'małopolskie', 'limanowski',
                                               'powiat')
    MALOPOLSKIE_LIMANOWSKI_MSZANA_DOLNA_WIEJSKA = ('1207092', 'Mszana Dolna', GminaType.WIEJSKA, 'małopolskie',
                                                   'limanowski', 'powiat')
    MALOPOLSKIE_LIMANOWSKI_NIEDZWIEDZ_WIEJSKA = ('1207102', 'Niedźwiedź', GminaType.WIEJSKA, 'małopolskie',
                                                 'limanowski', 'powiat')
    MALOPOLSKIE_LIMANOWSKI_SLOPNICE_WIEJSKA = ('1207112', 'Słopnice', GminaType.WIEJSKA, 'małopolskie', 'limanowski',
                                               'powiat')
    MALOPOLSKIE_LIMANOWSKI_TYMBARK_WIEJSKA = ('1207122', 'Tymbark', GminaType.WIEJSKA, 'małopolskie', 'limanowski',
                                              'powiat')
    MALOPOLSKIE_LIMANOWSKI_SZCZAWA_WIEJSKA = ('1207132', 'Szczawa', GminaType.WIEJSKA, 'małopolskie', 'limanowski',
                                              'powiat')
    MALOPOLSKIE_MIECHOWSKI_CHARSZNICA_WIEJSKA = ('1208012', 'Charsznica', GminaType.WIEJSKA, 'małopolskie',
                                                 'miechowski', 'powiat')
    MALOPOLSKIE_MIECHOWSKI_GOLCZA_WIEJSKA = ('1208022', 'Gołcza', GminaType.WIEJSKA, 'małopolskie', 'miechowski',
                                             'powiat')
    MALOPOLSKIE_MIECHOWSKI_KOZLOW_WIEJSKA = ('1208032', 'Kozłów', GminaType.WIEJSKA, 'małopolskie', 'miechowski',
                                             'powiat')
    MALOPOLSKIE_MIECHOWSKI_KSIAZ_WIELKI_MIEJSKO_WIEJSKA = ('1208043', 'Książ Wielki', GminaType.MIEJSKO_WIEJSKA,
                                                           'małopolskie', 'miechowski', 'powiat')
    MALOPOLSKIE_MIECHOWSKI_MIECHOW_MIEJSKO_WIEJSKA = ('1208053', 'Miechów', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                      'miechowski', 'powiat')
    MALOPOLSKIE_MIECHOWSKI_RACLAWICE_WIEJSKA = ('1208062', 'Racławice', GminaType.WIEJSKA, 'małopolskie', 'miechowski',
                                                'powiat')
    MALOPOLSKIE_MIECHOWSKI_SLABOSZOW_WIEJSKA = ('1208072', 'Słaboszów', GminaType.WIEJSKA, 'małopolskie', 'miechowski',
                                                'powiat')
    MALOPOLSKIE_MYSLENICKI_DOBCZYCE_MIEJSKO_WIEJSKA = ('1209013', 'Dobczyce', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                       'myślenicki', 'powiat')
    MALOPOLSKIE_MYSLENICKI_LUBIEN_WIEJSKA = ('1209022', 'Lubień', GminaType.WIEJSKA, 'małopolskie', 'myślenicki',
                                             'powiat')
    MALOPOLSKIE_MYSLENICKI_MYSLENICE_MIEJSKO_WIEJSKA = ('1209033', 'Myślenice', GminaType.MIEJSKO_WIEJSKA,
                                                        'małopolskie', 'myślenicki', 'powiat')
    MALOPOLSKIE_MYSLENICKI_PCIM_WIEJSKA = ('1209042', 'Pcim', GminaType.WIEJSKA, 'małopolskie', 'myślenicki', 'powiat')
    MALOPOLSKIE_MYSLENICKI_RACIECHOWICE_WIEJSKA = ('1209052', 'Raciechowice', GminaType.WIEJSKA, 'małopolskie',
                                                   'myślenicki', 'powiat')
    MALOPOLSKIE_MYSLENICKI_SIEPRAW_WIEJSKA = ('1209062', 'Siepraw', GminaType.WIEJSKA, 'małopolskie', 'myślenicki',
                                              'powiat')
    MALOPOLSKIE_MYSLENICKI_SULKOWICE_MIEJSKO_WIEJSKA = ('1209073', 'Sułkowice', GminaType.MIEJSKO_WIEJSKA,
                                                        'małopolskie', 'myślenicki', 'powiat')
    MALOPOLSKIE_MYSLENICKI_TOKARNIA_WIEJSKA = ('1209082', 'Tokarnia', GminaType.WIEJSKA, 'małopolskie', 'myślenicki',
                                               'powiat')
    MALOPOLSKIE_MYSLENICKI_WISNIOWA_WIEJSKA = ('1209092', 'Wiśniowa', GminaType.WIEJSKA, 'małopolskie', 'myślenicki',
                                               'powiat')
    MALOPOLSKIE_NOWOSADECKI_GRYBOW_MIEJSKA = ('1210011', 'Grybów', GminaType.MIEJSKA, 'małopolskie', 'nowosądecki',
                                              'powiat')
    MALOPOLSKIE_NOWOSADECKI_CHELMIEC_WIEJSKA = ('1210022', 'Chełmiec', GminaType.WIEJSKA, 'małopolskie', 'nowosądecki',
                                                'powiat')
    MALOPOLSKIE_NOWOSADECKI_GRODEK_NAD_DUNAJCEM_WIEJSKA = ('1210032', 'Gródek nad Dunajcem', GminaType.WIEJSKA,
                                                           'małopolskie', 'nowosądecki', 'powiat')
    MALOPOLSKIE_NOWOSADECKI_GRYBOW_WIEJSKA = ('1210042', 'Grybów', GminaType.WIEJSKA, 'małopolskie', 'nowosądecki',
                                              'powiat')
    MALOPOLSKIE_NOWOSADECKI_KAMIONKA_WIELKA_WIEJSKA = ('1210052', 'Kamionka Wielka', GminaType.WIEJSKA, 'małopolskie',
                                                       'nowosądecki', 'powiat')
    MALOPOLSKIE_NOWOSADECKI_KORZENNA_WIEJSKA = ('1210062', 'Korzenna', GminaType.WIEJSKA, 'małopolskie', 'nowosądecki',
                                                'powiat')
    MALOPOLSKIE_NOWOSADECKI_KRYNICA_ZDROJ_MIEJSKO_WIEJSKA = ('1210073', 'Krynica-Zdrój', GminaType.MIEJSKO_WIEJSKA,
                                                             'małopolskie', 'nowosądecki', 'powiat')
    MALOPOLSKIE_NOWOSADECKI_LABOWA_WIEJSKA = ('1210082', 'Łabowa', GminaType.WIEJSKA, 'małopolskie', 'nowosądecki',
                                              'powiat')
    MALOPOLSKIE_NOWOSADECKI_LACKO_WIEJSKA = ('1210092', 'Łącko', GminaType.WIEJSKA, 'małopolskie', 'nowosądecki',
                                             'powiat')
    MALOPOLSKIE_NOWOSADECKI_LOSOSINA_DOLNA_WIEJSKA = ('1210102', 'Łososina Dolna', GminaType.WIEJSKA, 'małopolskie',
                                                      'nowosądecki', 'powiat')
    MALOPOLSKIE_NOWOSADECKI_MUSZYNA_MIEJSKO_WIEJSKA = ('1210113', 'Muszyna', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                       'nowosądecki', 'powiat')
    MALOPOLSKIE_NOWOSADECKI_NAWOJOWA_WIEJSKA = ('1210122', 'Nawojowa', GminaType.WIEJSKA, 'małopolskie', 'nowosądecki',
                                                'powiat')
    MALOPOLSKIE_NOWOSADECKI_PIWNICZNA_ZDROJ_MIEJSKO_WIEJSKA = ('1210133', 'Piwniczna-Zdrój', GminaType.MIEJSKO_WIEJSKA,
                                                               'małopolskie', 'nowosądecki', 'powiat')
    MALOPOLSKIE_NOWOSADECKI_PODEGRODZIE_WIEJSKA = ('1210142', 'Podegrodzie', GminaType.WIEJSKA, 'małopolskie',
                                                   'nowosądecki', 'powiat')
    MALOPOLSKIE_NOWOSADECKI_RYTRO_WIEJSKA = ('1210152', 'Rytro', GminaType.WIEJSKA, 'małopolskie', 'nowosądecki',
                                             'powiat')
    MALOPOLSKIE_NOWOSADECKI_STARY_SACZ_MIEJSKO_WIEJSKA = ('1210163', 'Stary Sącz', GminaType.MIEJSKO_WIEJSKA,
                                                          'małopolskie', 'nowosądecki', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_NOWY_TARG_MIEJSKA = ('1211011', 'Nowy Targ', GminaType.MIEJSKA, 'małopolskie', 'nowotarski',
                                                'powiat')
    MALOPOLSKIE_NOWOTARSKI_SZCZAWNICA_MIEJSKO_WIEJSKA = ('1211023', 'Szczawnica', GminaType.MIEJSKO_WIEJSKA,
                                                         'małopolskie', 'nowotarski', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_CZARNY_DUNAJEC_MIEJSKO_WIEJSKA = ('1211033', 'Czarny Dunajec', GminaType.MIEJSKO_WIEJSKA,
                                                             'małopolskie', 'nowotarski', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_CZORSZTYN_WIEJSKA = ('1211042', 'Czorsztyn', GminaType.WIEJSKA, 'małopolskie', 'nowotarski',
                                                'powiat')
    MALOPOLSKIE_NOWOTARSKI_JABLONKA_WIEJSKA = ('1211052', 'Jabłonka', GminaType.WIEJSKA, 'małopolskie', 'nowotarski',
                                               'powiat')
    MALOPOLSKIE_NOWOTARSKI_KROSCIENKO_NAD_DUNAJCEM_WIEJSKA = ('1211062', 'Krościenko nad Dunajcem', GminaType.WIEJSKA,
                                                              'małopolskie', 'nowotarski', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_LIPNICA_WIELKA_WIEJSKA = ('1211072', 'Lipnica Wielka', GminaType.WIEJSKA, 'małopolskie',
                                                     'nowotarski', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_LAPSZE_NIZNE_WIEJSKA = ('1211082', 'Łapsze Niżne', GminaType.WIEJSKA, 'małopolskie',
                                                   'nowotarski', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_NOWY_TARG_WIEJSKA = ('1211092', 'Nowy Targ', GminaType.WIEJSKA, 'małopolskie', 'nowotarski',
                                                'powiat')
    MALOPOLSKIE_NOWOTARSKI_OCHOTNICA_DOLNA_WIEJSKA = ('1211102', 'Ochotnica Dolna', GminaType.WIEJSKA, 'małopolskie',
                                                      'nowotarski', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_RABA_WYZNA_WIEJSKA = ('1211112', 'Raba Wyżna', GminaType.WIEJSKA, 'małopolskie',
                                                 'nowotarski', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_RABKA_ZDROJ_MIEJSKO_WIEJSKA = ('1211123', 'Rabka-Zdrój', GminaType.MIEJSKO_WIEJSKA,
                                                          'małopolskie', 'nowotarski', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_SPYTKOWICE_WIEJSKA = ('1211132', 'Spytkowice', GminaType.WIEJSKA, 'małopolskie',
                                                 'nowotarski', 'powiat')
    MALOPOLSKIE_NOWOTARSKI_SZAFLARY_WIEJSKA = ('1211142', 'Szaflary', GminaType.WIEJSKA, 'małopolskie', 'nowotarski',
                                               'powiat')
    MALOPOLSKIE_OLKUSKI_BUKOWNO_MIEJSKA = ('1212011', 'Bukowno', GminaType.MIEJSKA, 'małopolskie', 'olkuski', 'powiat')
    MALOPOLSKIE_OLKUSKI_BOLESLAW_WIEJSKA = ('1212032', 'Bolesław', GminaType.WIEJSKA, 'małopolskie', 'olkuski',
                                            'powiat')
    MALOPOLSKIE_OLKUSKI_KLUCZE_WIEJSKA = ('1212042', 'Klucze', GminaType.WIEJSKA, 'małopolskie', 'olkuski', 'powiat')
    MALOPOLSKIE_OLKUSKI_OLKUSZ_MIEJSKO_WIEJSKA = ('1212053', 'Olkusz', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                  'olkuski', 'powiat')
    MALOPOLSKIE_OLKUSKI_TRZYCIAZ_WIEJSKA = ('1212062', 'Trzyciąż', GminaType.WIEJSKA, 'małopolskie', 'olkuski',
                                            'powiat')
    MALOPOLSKIE_OLKUSKI_WOLBROM_MIEJSKO_WIEJSKA = ('1212073', 'Wolbrom', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                   'olkuski', 'powiat')
    MALOPOLSKIE_OSWIECIMSKI_OSWIECIM_MIEJSKA = ('1213011', 'Oświęcim', GminaType.MIEJSKA, 'małopolskie', 'oświęcimski',
                                                'powiat')
    MALOPOLSKIE_OSWIECIMSKI_BRZESZCZE_MIEJSKO_WIEJSKA = ('1213023', 'Brzeszcze', GminaType.MIEJSKO_WIEJSKA,
                                                         'małopolskie', 'oświęcimski', 'powiat')
    MALOPOLSKIE_OSWIECIMSKI_CHELMEK_MIEJSKO_WIEJSKA = ('1213033', 'Chełmek', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                       'oświęcimski', 'powiat')
    MALOPOLSKIE_OSWIECIMSKI_KETY_MIEJSKO_WIEJSKA = ('1213043', 'Kęty', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                    'oświęcimski', 'powiat')
    MALOPOLSKIE_OSWIECIMSKI_OSIEK_WIEJSKA = ('1213052', 'Osiek', GminaType.WIEJSKA, 'małopolskie', 'oświęcimski',
                                             'powiat')
    MALOPOLSKIE_OSWIECIMSKI_OSWIECIM_WIEJSKA = ('1213062', 'Oświęcim', GminaType.WIEJSKA, 'małopolskie', 'oświęcimski',
                                                'powiat')
    MALOPOLSKIE_OSWIECIMSKI_POLANKA_WIELKA_WIEJSKA = ('1213072', 'Polanka Wielka', GminaType.WIEJSKA, 'małopolskie',
                                                      'oświęcimski', 'powiat')
    MALOPOLSKIE_OSWIECIMSKI_PRZECISZOW_WIEJSKA = ('1213082', 'Przeciszów', GminaType.WIEJSKA, 'małopolskie',
                                                  'oświęcimski', 'powiat')
    MALOPOLSKIE_OSWIECIMSKI_ZATOR_MIEJSKO_WIEJSKA = ('1213093', 'Zator', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                     'oświęcimski', 'powiat')
    MALOPOLSKIE_PROSZOWICKI_KONIUSZA_WIEJSKA = ('1214012', 'Koniusza', GminaType.WIEJSKA, 'małopolskie', 'proszowicki',
                                                'powiat')
    MALOPOLSKIE_PROSZOWICKI_KOSZYCE_MIEJSKO_WIEJSKA = ('1214023', 'Koszyce', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                       'proszowicki', 'powiat')
    MALOPOLSKIE_PROSZOWICKI_NOWE_BRZESKO_MIEJSKO_WIEJSKA = ('1214033', 'Nowe Brzesko', GminaType.MIEJSKO_WIEJSKA,
                                                            'małopolskie', 'proszowicki', 'powiat')
    MALOPOLSKIE_PROSZOWICKI_PALECZNICA_WIEJSKA = ('1214042', 'Pałecznica', GminaType.WIEJSKA, 'małopolskie',
                                                  'proszowicki', 'powiat')
    MALOPOLSKIE_PROSZOWICKI_PROSZOWICE_MIEJSKO_WIEJSKA = ('1214053', 'Proszowice', GminaType.MIEJSKO_WIEJSKA,
                                                          'małopolskie', 'proszowicki', 'powiat')
    MALOPOLSKIE_PROSZOWICKI_RADZIEMICE_WIEJSKA = ('1214062', 'Radziemice', GminaType.WIEJSKA, 'małopolskie',
                                                  'proszowicki', 'powiat')
    MALOPOLSKIE_SUSKI_JORDANOW_MIEJSKA = ('1215011', 'Jordanów', GminaType.MIEJSKA, 'małopolskie', 'suski', 'powiat')
    MALOPOLSKIE_SUSKI_SUCHA_BESKIDZKA_MIEJSKA = ('1215021', 'Sucha Beskidzka', GminaType.MIEJSKA, 'małopolskie',
                                                 'suski', 'powiat')
    MALOPOLSKIE_SUSKI_BUDZOW_WIEJSKA = ('1215032', 'Budzów', GminaType.WIEJSKA, 'małopolskie', 'suski', 'powiat')
    MALOPOLSKIE_SUSKI_BYSTRA_SIDZINA_WIEJSKA = ('1215042', 'Bystra-Sidzina', GminaType.WIEJSKA, 'małopolskie', 'suski',
                                                'powiat')
    MALOPOLSKIE_SUSKI_JORDANOW_WIEJSKA = ('1215052', 'Jordanów', GminaType.WIEJSKA, 'małopolskie', 'suski', 'powiat')
    MALOPOLSKIE_SUSKI_MAKOW_PODHALANSKI_MIEJSKO_WIEJSKA = ('1215063', 'Maków Podhalański', GminaType.MIEJSKO_WIEJSKA,
                                                           'małopolskie', 'suski', 'powiat')
    MALOPOLSKIE_SUSKI_STRYSZAWA_WIEJSKA = ('1215072', 'Stryszawa', GminaType.WIEJSKA, 'małopolskie', 'suski', 'powiat')
    MALOPOLSKIE_SUSKI_ZAWOJA_WIEJSKA = ('1215082', 'Zawoja', GminaType.WIEJSKA, 'małopolskie', 'suski', 'powiat')
    MALOPOLSKIE_SUSKI_ZEMBRZYCE_WIEJSKA = ('1215092', 'Zembrzyce', GminaType.WIEJSKA, 'małopolskie', 'suski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_CIEZKOWICE_MIEJSKO_WIEJSKA = ('1216013', 'Ciężkowice', GminaType.MIEJSKO_WIEJSKA,
                                                        'małopolskie', 'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_GROMNIK_WIEJSKA = ('1216022', 'Gromnik', GminaType.WIEJSKA, 'małopolskie', 'tarnowski',
                                             'powiat')
    MALOPOLSKIE_TARNOWSKI_LISIA_GORA_WIEJSKA = ('1216032', 'Lisia Góra', GminaType.WIEJSKA, 'małopolskie', 'tarnowski',
                                                'powiat')
    MALOPOLSKIE_TARNOWSKI_PLESNA_WIEJSKA = ('1216042', 'Pleśna', GminaType.WIEJSKA, 'małopolskie', 'tarnowski',
                                            'powiat')
    MALOPOLSKIE_TARNOWSKI_RADLOW_MIEJSKO_WIEJSKA = ('1216053', 'Radłów', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                    'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_RYGLICE_MIEJSKO_WIEJSKA = ('1216063', 'Ryglice', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                     'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_RZEPIENNIK_STRZYZEWSKI_WIEJSKA = ('1216072', 'Rzepiennik Strzyżewski', GminaType.WIEJSKA,
                                                            'małopolskie', 'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_SKRZYSZOW_WIEJSKA = ('1216082', 'Skrzyszów', GminaType.WIEJSKA, 'małopolskie', 'tarnowski',
                                               'powiat')
    MALOPOLSKIE_TARNOWSKI_TARNOW_WIEJSKA = ('1216092', 'Tarnów', GminaType.WIEJSKA, 'małopolskie', 'tarnowski',
                                            'powiat')
    MALOPOLSKIE_TARNOWSKI_TUCHOW_MIEJSKO_WIEJSKA = ('1216103', 'Tuchów', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                    'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_WIERZCHOSLAWICE_WIEJSKA = ('1216112', 'Wierzchosławice', GminaType.WIEJSKA, 'małopolskie',
                                                     'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_WIETRZYCHOWICE_WIEJSKA = ('1216122', 'Wietrzychowice', GminaType.WIEJSKA, 'małopolskie',
                                                    'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_WOJNICZ_MIEJSKO_WIEJSKA = ('1216133', 'Wojnicz', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                     'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_ZAKLICZYN_MIEJSKO_WIEJSKA = ('1216143', 'Zakliczyn', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                       'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_ZABNO_MIEJSKO_WIEJSKA = ('1216153', 'Żabno', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                   'tarnowski', 'powiat')
    MALOPOLSKIE_TARNOWSKI_SZERZYNY_WIEJSKA = ('1216162', 'Szerzyny', GminaType.WIEJSKA, 'małopolskie', 'tarnowski',
                                              'powiat')
    MALOPOLSKIE_TATRZANSKI_ZAKOPANE_MIEJSKA = ('1217011', 'Zakopane', GminaType.MIEJSKA, 'małopolskie', 'tatrzański',
                                               'powiat')
    MALOPOLSKIE_TATRZANSKI_BIALY_DUNAJEC_WIEJSKA = ('1217022', 'Biały Dunajec', GminaType.WIEJSKA, 'małopolskie',
                                                    'tatrzański', 'powiat')
    MALOPOLSKIE_TATRZANSKI_BUKOWINA_TATRZANSKA_WIEJSKA = ('1217032', 'Bukowina Tatrzańska', GminaType.WIEJSKA,
                                                          'małopolskie', 'tatrzański', 'powiat')
    MALOPOLSKIE_TATRZANSKI_KOSCIELISKO_WIEJSKA = ('1217042', 'Kościelisko', GminaType.WIEJSKA, 'małopolskie',
                                                  'tatrzański', 'powiat')
    MALOPOLSKIE_TATRZANSKI_PORONIN_WIEJSKA = ('1217052', 'Poronin', GminaType.WIEJSKA, 'małopolskie', 'tatrzański',
                                              'powiat')
    MALOPOLSKIE_WADOWICKI_ANDRYCHOW_MIEJSKO_WIEJSKA = ('1218013', 'Andrychów', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                       'wadowicki', 'powiat')
    MALOPOLSKIE_WADOWICKI_BRZEZNICA_WIEJSKA = ('1218022', 'Brzeźnica', GminaType.WIEJSKA, 'małopolskie', 'wadowicki',
                                               'powiat')
    MALOPOLSKIE_WADOWICKI_KALWARIA_ZEBRZYDOWSKA_MIEJSKO_WIEJSKA = ('1218033', 'Kalwaria Zebrzydowska',
                                                                   GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                                   'wadowicki', 'powiat')
    MALOPOLSKIE_WADOWICKI_LANCKORONA_WIEJSKA = ('1218042', 'Lanckorona', GminaType.WIEJSKA, 'małopolskie', 'wadowicki',
                                                'powiat')
    MALOPOLSKIE_WADOWICKI_MUCHARZ_WIEJSKA = ('1218052', 'Mucharz', GminaType.WIEJSKA, 'małopolskie', 'wadowicki',
                                             'powiat')
    MALOPOLSKIE_WADOWICKI_SPYTKOWICE_WIEJSKA = ('1218062', 'Spytkowice', GminaType.WIEJSKA, 'małopolskie', 'wadowicki',
                                                'powiat')
    MALOPOLSKIE_WADOWICKI_STRYSZOW_WIEJSKA = ('1218072', 'Stryszów', GminaType.WIEJSKA, 'małopolskie', 'wadowicki',
                                              'powiat')
    MALOPOLSKIE_WADOWICKI_TOMICE_WIEJSKA = ('1218082', 'Tomice', GminaType.WIEJSKA, 'małopolskie', 'wadowicki',
                                            'powiat')
    MALOPOLSKIE_WADOWICKI_WADOWICE_MIEJSKO_WIEJSKA = ('1218093', 'Wadowice', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                      'wadowicki', 'powiat')
    MALOPOLSKIE_WADOWICKI_WIEPRZ_WIEJSKA = ('1218102', 'Wieprz', GminaType.WIEJSKA, 'małopolskie', 'wadowicki',
                                            'powiat')
    MALOPOLSKIE_WIELICKI_BISKUPICE_WIEJSKA = ('1219012', 'Biskupice', GminaType.WIEJSKA, 'małopolskie', 'wielicki',
                                              'powiat')
    MALOPOLSKIE_WIELICKI_GDOW_WIEJSKA = ('1219022', 'Gdów', GminaType.WIEJSKA, 'małopolskie', 'wielicki', 'powiat')
    MALOPOLSKIE_WIELICKI_KLAJ_WIEJSKA = ('1219032', 'Kłaj', GminaType.WIEJSKA, 'małopolskie', 'wielicki', 'powiat')
    MALOPOLSKIE_WIELICKI_NIEPOLOMICE_MIEJSKO_WIEJSKA = ('1219043', 'Niepołomice', GminaType.MIEJSKO_WIEJSKA,
                                                        'małopolskie', 'wielicki', 'powiat')
    MALOPOLSKIE_WIELICKI_WIELICZKA_MIEJSKO_WIEJSKA = ('1219053', 'Wieliczka', GminaType.MIEJSKO_WIEJSKA, 'małopolskie',
                                                      'wielicki', 'powiat')
    MALOPOLSKIE_KRAKOW_KRAKOW_MIEJSKA = ('1261011', 'Kraków', GminaType.MIEJSKA, 'małopolskie', 'Kraków',
                                         'miasto na prawach powiatu')
    MALOPOLSKIE_NOWY_SACZ_NOWY_SACZ_MIEJSKA = ('1262011', 'Nowy Sącz', GminaType.MIEJSKA, 'małopolskie', 'Nowy Sącz',
                                               'miasto na prawach powiatu')
    MALOPOLSKIE_TARNOW_TARNOW_MIEJSKA = ('1263011', 'Tarnów', GminaType.MIEJSKA, 'małopolskie', 'Tarnów',
                                         'miasto na prawach powiatu')

    # Mazowieckie
    MAZOWIECKIE_BIALOBRZESKI_BIALOBRZEGI_MIEJSKO_WIEJSKA = ('1401013', 'Białobrzegi', GminaType.MIEJSKO_WIEJSKA,
                                                            'mazowieckie', 'białobrzeski', 'powiat')
    MAZOWIECKIE_BIALOBRZESKI_PROMNA_WIEJSKA = ('1401022', 'Promna', GminaType.WIEJSKA, 'mazowieckie', 'białobrzeski',
                                               'powiat')
    MAZOWIECKIE_BIALOBRZESKI_RADZANOW_WIEJSKA = ('1401032', 'Radzanów', GminaType.WIEJSKA, 'mazowieckie',
                                                 'białobrzeski', 'powiat')
    MAZOWIECKIE_BIALOBRZESKI_STARA_BLOTNICA_WIEJSKA = ('1401042', 'Stara Błotnica', GminaType.WIEJSKA, 'mazowieckie',
                                                       'białobrzeski', 'powiat')
    MAZOWIECKIE_BIALOBRZESKI_STROMIEC_WIEJSKA = ('1401052', 'Stromiec', GminaType.WIEJSKA, 'mazowieckie',
                                                 'białobrzeski', 'powiat')
    MAZOWIECKIE_BIALOBRZESKI_WYSMIERZYCE_MIEJSKO_WIEJSKA = ('1401063', 'Wyśmierzyce', GminaType.MIEJSKO_WIEJSKA,
                                                            'mazowieckie', 'białobrzeski', 'powiat')
    MAZOWIECKIE_CIECHANOWSKI_CIECHANOW_MIEJSKA = ('1402011', 'Ciechanów', GminaType.MIEJSKA, 'mazowieckie',
                                                  'ciechanowski', 'powiat')
    MAZOWIECKIE_CIECHANOWSKI_CIECHANOW_WIEJSKA = ('1402022', 'Ciechanów', GminaType.WIEJSKA, 'mazowieckie',
                                                  'ciechanowski', 'powiat')
    MAZOWIECKIE_CIECHANOWSKI_GLINOJECK_MIEJSKO_WIEJSKA = ('1402033', 'Glinojeck', GminaType.MIEJSKO_WIEJSKA,
                                                          'mazowieckie', 'ciechanowski', 'powiat')
    MAZOWIECKIE_CIECHANOWSKI_GOLYMIN_OSRODEK_WIEJSKA = ('1402042', 'Gołymin-Ośrodek', GminaType.WIEJSKA, 'mazowieckie',
                                                        'ciechanowski', 'powiat')
    MAZOWIECKIE_CIECHANOWSKI_GRUDUSK_WIEJSKA = ('1402052', 'Grudusk', GminaType.WIEJSKA, 'mazowieckie', 'ciechanowski',
                                                'powiat')
    MAZOWIECKIE_CIECHANOWSKI_OJRZEN_WIEJSKA = ('1402062', 'Ojrzeń', GminaType.WIEJSKA, 'mazowieckie', 'ciechanowski',
                                               'powiat')
    MAZOWIECKIE_CIECHANOWSKI_OPINOGORA_GORNA_WIEJSKA = ('1402072', 'Opinogóra Górna', GminaType.WIEJSKA, 'mazowieckie',
                                                        'ciechanowski', 'powiat')
    MAZOWIECKIE_CIECHANOWSKI_REGIMIN_WIEJSKA = ('1402082', 'Regimin', GminaType.WIEJSKA, 'mazowieckie', 'ciechanowski',
                                                'powiat')
    MAZOWIECKIE_CIECHANOWSKI_SONSK_WIEJSKA = ('1402092', 'Sońsk', GminaType.WIEJSKA, 'mazowieckie', 'ciechanowski',
                                              'powiat')
    MAZOWIECKIE_GARWOLINSKI_GARWOLIN_MIEJSKA = ('1403011', 'Garwolin', GminaType.MIEJSKA, 'mazowieckie', 'garwoliński',
                                                'powiat')
    MAZOWIECKIE_GARWOLINSKI_LASKARZEW_MIEJSKA = ('1403021', 'Łaskarzew', GminaType.MIEJSKA, 'mazowieckie',
                                                 'garwoliński', 'powiat')
    MAZOWIECKIE_GARWOLINSKI_BOROWIE_WIEJSKA = ('1403032', 'Borowie', GminaType.WIEJSKA, 'mazowieckie', 'garwoliński',
                                               'powiat')
    MAZOWIECKIE_GARWOLINSKI_GARWOLIN_WIEJSKA = ('1403042', 'Garwolin', GminaType.WIEJSKA, 'mazowieckie', 'garwoliński',
                                                'powiat')
    MAZOWIECKIE_GARWOLINSKI_GORZNO_WIEJSKA = ('1403052', 'Górzno', GminaType.WIEJSKA, 'mazowieckie', 'garwoliński',
                                              'powiat')
    MAZOWIECKIE_GARWOLINSKI_LASKARZEW_WIEJSKA = ('1403062', 'Łaskarzew', GminaType.WIEJSKA, 'mazowieckie',
                                                 'garwoliński', 'powiat')
    MAZOWIECKIE_GARWOLINSKI_MACIEJOWICE_MIEJSKO_WIEJSKA = ('1403073', 'Maciejowice', GminaType.MIEJSKO_WIEJSKA,
                                                           'mazowieckie', 'garwoliński', 'powiat')
    MAZOWIECKIE_GARWOLINSKI_MIASTKOW_KOSCIELNY_WIEJSKA = ('1403082', 'Miastków Kościelny', GminaType.WIEJSKA,
                                                          'mazowieckie', 'garwoliński', 'powiat')
    MAZOWIECKIE_GARWOLINSKI_PARYSOW_WIEJSKA = ('1403092', 'Parysów', GminaType.WIEJSKA, 'mazowieckie', 'garwoliński',
                                               'powiat')
    MAZOWIECKIE_GARWOLINSKI_PILAWA_MIEJSKO_WIEJSKA = ('1403103', 'Pilawa', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                      'garwoliński', 'powiat')
    MAZOWIECKIE_GARWOLINSKI_SOBOLEW_WIEJSKA = ('1403112', 'Sobolew', GminaType.WIEJSKA, 'mazowieckie', 'garwoliński',
                                               'powiat')
    MAZOWIECKIE_GARWOLINSKI_TROJANOW_WIEJSKA = ('1403122', 'Trojanów', GminaType.WIEJSKA, 'mazowieckie', 'garwoliński',
                                                'powiat')
    MAZOWIECKIE_GARWOLINSKI_WILGA_WIEJSKA = ('1403132', 'Wilga', GminaType.WIEJSKA, 'mazowieckie', 'garwoliński',
                                             'powiat')
    MAZOWIECKIE_GARWOLINSKI_ZELECHOW_MIEJSKO_WIEJSKA = ('1403143', 'Żelechów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                        'garwoliński', 'powiat')
    MAZOWIECKIE_GOSTYNINSKI_GOSTYNIN_MIEJSKA = ('1404011', 'Gostynin', GminaType.MIEJSKA, 'mazowieckie', 'gostyniński',
                                                'powiat')
    MAZOWIECKIE_GOSTYNINSKI_GOSTYNIN_WIEJSKA = ('1404022', 'Gostynin', GminaType.WIEJSKA, 'mazowieckie', 'gostyniński',
                                                'powiat')
    MAZOWIECKIE_GOSTYNINSKI_PACYNA_WIEJSKA = ('1404032', 'Pacyna', GminaType.WIEJSKA, 'mazowieckie', 'gostyniński',
                                              'powiat')
    MAZOWIECKIE_GOSTYNINSKI_SANNIKI_MIEJSKO_WIEJSKA = ('1404043', 'Sanniki', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                       'gostyniński', 'powiat')
    MAZOWIECKIE_GOSTYNINSKI_SZCZAWIN_KOSCIELNY_WIEJSKA = ('1404052', 'Szczawin Kościelny', GminaType.WIEJSKA,
                                                          'mazowieckie', 'gostyniński', 'powiat')
    MAZOWIECKIE_GRODZISKI_MILANOWEK_MIEJSKA = ('1405011', 'Milanówek', GminaType.MIEJSKA, 'mazowieckie', 'grodziski',
                                               'powiat')
    MAZOWIECKIE_GRODZISKI_PODKOWA_LESNA_MIEJSKA = ('1405021', 'Podkowa Leśna', GminaType.MIEJSKA, 'mazowieckie',
                                                   'grodziski', 'powiat')
    MAZOWIECKIE_GRODZISKI_BARANOW_WIEJSKA = ('1405032', 'Baranów', GminaType.WIEJSKA, 'mazowieckie', 'grodziski',
                                             'powiat')
    MAZOWIECKIE_GRODZISKI_GRODZISK_MAZOWIECKI_MIEJSKO_WIEJSKA = ('1405043', 'Grodzisk Mazowiecki',
                                                                 GminaType.MIEJSKO_WIEJSKA, 'mazowieckie', 'grodziski',
                                                                 'powiat')
    MAZOWIECKIE_GRODZISKI_JAKTOROW_WIEJSKA = ('1405052', 'Jaktorów', GminaType.WIEJSKA, 'mazowieckie', 'grodziski',
                                              'powiat')
    MAZOWIECKIE_GRODZISKI_ZABIA_WOLA_WIEJSKA = ('1405062', 'Żabia Wola', GminaType.WIEJSKA, 'mazowieckie', 'grodziski',
                                                'powiat')
    MAZOWIECKIE_GROJECKI_BELSK_DUZY_WIEJSKA = ('1406012', 'Belsk Duży', GminaType.WIEJSKA, 'mazowieckie', 'grójecki',
                                               'powiat')
    MAZOWIECKIE_GROJECKI_BLEDOW_WIEJSKA = ('1406022', 'Błędów', GminaType.WIEJSKA, 'mazowieckie', 'grójecki', 'powiat')
    MAZOWIECKIE_GROJECKI_CHYNOW_WIEJSKA = ('1406032', 'Chynów', GminaType.WIEJSKA, 'mazowieckie', 'grójecki', 'powiat')
    MAZOWIECKIE_GROJECKI_GOSZCZYN_WIEJSKA = ('1406042', 'Goszczyn', GminaType.WIEJSKA, 'mazowieckie', 'grójecki',
                                             'powiat')
    MAZOWIECKIE_GROJECKI_GROJEC_MIEJSKO_WIEJSKA = ('1406053', 'Grójec', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                   'grójecki', 'powiat')
    MAZOWIECKIE_GROJECKI_JASIENIEC_WIEJSKA = ('1406062', 'Jasieniec', GminaType.WIEJSKA, 'mazowieckie', 'grójecki',
                                              'powiat')
    MAZOWIECKIE_GROJECKI_MOGIELNICA_MIEJSKO_WIEJSKA = ('1406073', 'Mogielnica', GminaType.MIEJSKO_WIEJSKA,
                                                       'mazowieckie', 'grójecki', 'powiat')
    MAZOWIECKIE_GROJECKI_NOWE_MIASTO_NAD_PILICA_MIEJSKO_WIEJSKA = ('1406083', 'Nowe Miasto nad Pilicą',
                                                                   GminaType.MIEJSKO_WIEJSKA, 'mazowieckie', 'grójecki',
                                                                   'powiat')
    MAZOWIECKIE_GROJECKI_PNIEWY_WIEJSKA = ('1406092', 'Pniewy', GminaType.WIEJSKA, 'mazowieckie', 'grójecki', 'powiat')
    MAZOWIECKIE_GROJECKI_WARKA_MIEJSKO_WIEJSKA = ('1406113', 'Warka', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                  'grójecki', 'powiat')
    MAZOWIECKIE_KOZIENICKI_GARBATKA_LETNISKO_WIEJSKA = ('1407012', 'Garbatka-Letnisko', GminaType.WIEJSKA,
                                                        'mazowieckie', 'kozienicki', 'powiat')
    MAZOWIECKIE_KOZIENICKI_GLOWACZOW_MIEJSKO_WIEJSKA = ('1407023', 'Głowaczów', GminaType.MIEJSKO_WIEJSKA,
                                                        'mazowieckie', 'kozienicki', 'powiat')
    MAZOWIECKIE_KOZIENICKI_GNIEWOSZOW_WIEJSKA = ('1407032', 'Gniewoszów', GminaType.WIEJSKA, 'mazowieckie',
                                                 'kozienicki', 'powiat')
    MAZOWIECKIE_KOZIENICKI_GRABOW_NAD_PILICA_WIEJSKA = ('1407042', 'Grabów nad Pilicą', GminaType.WIEJSKA,
                                                        'mazowieckie', 'kozienicki', 'powiat')
    MAZOWIECKIE_KOZIENICKI_KOZIENICE_MIEJSKO_WIEJSKA = ('1407053', 'Kozienice', GminaType.MIEJSKO_WIEJSKA,
                                                        'mazowieckie', 'kozienicki', 'powiat')
    MAZOWIECKIE_KOZIENICKI_MAGNUSZEW_MIEJSKO_WIEJSKA = ('1407063', 'Magnuszew', GminaType.MIEJSKO_WIEJSKA,
                                                        'mazowieckie', 'kozienicki', 'powiat')
    MAZOWIECKIE_KOZIENICKI_SIECIECHOW_WIEJSKA = ('1407072', 'Sieciechów', GminaType.WIEJSKA, 'mazowieckie',
                                                 'kozienicki', 'powiat')
    MAZOWIECKIE_LEGIONOWSKI_LEGIONOWO_MIEJSKA = ('1408011', 'Legionowo', GminaType.MIEJSKA, 'mazowieckie',
                                                 'legionowski', 'powiat')
    MAZOWIECKIE_LEGIONOWSKI_JABLONNA_WIEJSKA = ('1408022', 'Jabłonna', GminaType.WIEJSKA, 'mazowieckie', 'legionowski',
                                                'powiat')
    MAZOWIECKIE_LEGIONOWSKI_NIEPORET_WIEJSKA = ('1408032', 'Nieporęt', GminaType.WIEJSKA, 'mazowieckie', 'legionowski',
                                                'powiat')
    MAZOWIECKIE_LEGIONOWSKI_SEROCK_MIEJSKO_WIEJSKA = ('1408043', 'Serock', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                      'legionowski', 'powiat')
    MAZOWIECKIE_LEGIONOWSKI_WIELISZEW_WIEJSKA = ('1408052', 'Wieliszew', GminaType.WIEJSKA, 'mazowieckie',
                                                 'legionowski', 'powiat')
    MAZOWIECKIE_LIPSKI_CHOTCZA_WIEJSKA = ('1409012', 'Chotcza', GminaType.WIEJSKA, 'mazowieckie', 'lipski', 'powiat')
    MAZOWIECKIE_LIPSKI_CIEPIELOW_MIEJSKO_WIEJSKA = ('1409023', 'Ciepielów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                    'lipski', 'powiat')
    MAZOWIECKIE_LIPSKI_LIPSKO_MIEJSKO_WIEJSKA = ('1409033', 'Lipsko', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                 'lipski', 'powiat')
    MAZOWIECKIE_LIPSKI_RZECZNIOW_WIEJSKA = ('1409042', 'Rzeczniów', GminaType.WIEJSKA, 'mazowieckie', 'lipski',
                                            'powiat')
    MAZOWIECKIE_LIPSKI_SIENNO_MIEJSKO_WIEJSKA = ('1409053', 'Sienno', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                 'lipski', 'powiat')
    MAZOWIECKIE_LIPSKI_SOLEC_NAD_WISLA_MIEJSKO_WIEJSKA = ('1409063', 'Solec nad Wisłą', GminaType.MIEJSKO_WIEJSKA,
                                                          'mazowieckie', 'lipski', 'powiat')
    MAZOWIECKIE_LOSICKI_HUSZLEW_WIEJSKA = ('1410012', 'Huszlew', GminaType.WIEJSKA, 'mazowieckie', 'łosicki', 'powiat')
    MAZOWIECKIE_LOSICKI_LOSICE_MIEJSKO_WIEJSKA = ('1410023', 'Łosice', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                  'łosicki', 'powiat')
    MAZOWIECKIE_LOSICKI_OLSZANKA_WIEJSKA = ('1410032', 'Olszanka', GminaType.WIEJSKA, 'mazowieckie', 'łosicki',
                                            'powiat')
    MAZOWIECKIE_LOSICKI_PLATEROW_WIEJSKA = ('1410042', 'Platerów', GminaType.WIEJSKA, 'mazowieckie', 'łosicki',
                                            'powiat')
    MAZOWIECKIE_LOSICKI_SARNAKI_WIEJSKA = ('1410052', 'Sarnaki', GminaType.WIEJSKA, 'mazowieckie', 'łosicki', 'powiat')
    MAZOWIECKIE_LOSICKI_STARA_KORNICA_WIEJSKA = ('1410062', 'Stara Kornica', GminaType.WIEJSKA, 'mazowieckie',
                                                 'łosicki', 'powiat')
    MAZOWIECKIE_MAKOWSKI_MAKOW_MAZOWIECKI_MIEJSKA = ('1411011', 'Maków Mazowiecki', GminaType.MIEJSKA, 'mazowieckie',
                                                     'makowski', 'powiat')
    MAZOWIECKIE_MAKOWSKI_CZERWONKA_WIEJSKA = ('1411022', 'Czerwonka', GminaType.WIEJSKA, 'mazowieckie', 'makowski',
                                              'powiat')
    MAZOWIECKIE_MAKOWSKI_KARNIEWO_WIEJSKA = ('1411032', 'Karniewo', GminaType.WIEJSKA, 'mazowieckie', 'makowski',
                                             'powiat')
    MAZOWIECKIE_MAKOWSKI_KRASNOSIELC_WIEJSKA = ('1411042', 'Krasnosielc', GminaType.WIEJSKA, 'mazowieckie', 'makowski',
                                                'powiat')
    MAZOWIECKIE_MAKOWSKI_MLYNARZE_WIEJSKA = ('1411052', 'Młynarze', GminaType.WIEJSKA, 'mazowieckie', 'makowski',
                                             'powiat')
    MAZOWIECKIE_MAKOWSKI_PLONIAWY_BRAMURA_WIEJSKA = ('1411062', 'Płoniawy-Bramura', GminaType.WIEJSKA, 'mazowieckie',
                                                     'makowski', 'powiat')
    MAZOWIECKIE_MAKOWSKI_ROZAN_MIEJSKO_WIEJSKA = ('1411073', 'Różan', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                  'makowski', 'powiat')
    MAZOWIECKIE_MAKOWSKI_RZEWNIE_WIEJSKA = ('1411082', 'Rzewnie', GminaType.WIEJSKA, 'mazowieckie', 'makowski',
                                            'powiat')
    MAZOWIECKIE_MAKOWSKI_SYPNIEWO_WIEJSKA = ('1411092', 'Sypniewo', GminaType.WIEJSKA, 'mazowieckie', 'makowski',
                                             'powiat')
    MAZOWIECKIE_MAKOWSKI_SZELKOW_WIEJSKA = ('1411102', 'Szelków', GminaType.WIEJSKA, 'mazowieckie', 'makowski',
                                            'powiat')
    MAZOWIECKIE_MINSKI_MINSK_MAZOWIECKI_MIEJSKA = ('1412011', 'Mińsk Mazowiecki', GminaType.MIEJSKA, 'mazowieckie',
                                                   'miński', 'powiat')
    MAZOWIECKIE_MINSKI_CEGLOW_MIEJSKO_WIEJSKA = ('1412043', 'Cegłów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                 'miński', 'powiat')
    MAZOWIECKIE_MINSKI_DEBE_WIELKIE_WIEJSKA = ('1412052', 'Dębe Wielkie', GminaType.WIEJSKA, 'mazowieckie', 'miński',
                                               'powiat')
    MAZOWIECKIE_MINSKI_DOBRE_MIEJSKO_WIEJSKA = ('1412063', 'Dobre', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie', 'miński',
                                                'powiat')
    MAZOWIECKIE_MINSKI_HALINOW_MIEJSKO_WIEJSKA = ('1412073', 'Halinów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                  'miński', 'powiat')
    MAZOWIECKIE_MINSKI_JAKUBOW_WIEJSKA = ('1412082', 'Jakubów', GminaType.WIEJSKA, 'mazowieckie', 'miński', 'powiat')
    MAZOWIECKIE_MINSKI_KALUSZYN_MIEJSKO_WIEJSKA = ('1412093', 'Kałuszyn', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                   'miński', 'powiat')
    MAZOWIECKIE_MINSKI_LATOWICZ_MIEJSKO_WIEJSKA = ('1412103', 'Latowicz', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                   'miński', 'powiat')
    MAZOWIECKIE_MINSKI_MINSK_MAZOWIECKI_WIEJSKA = ('1412112', 'Mińsk Mazowiecki', GminaType.WIEJSKA, 'mazowieckie',
                                                   'miński', 'powiat')
    MAZOWIECKIE_MINSKI_MROZY_MIEJSKO_WIEJSKA = ('1412123', 'Mrozy', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie', 'miński',
                                                'powiat')
    MAZOWIECKIE_MINSKI_SIENNICA_MIEJSKO_WIEJSKA = ('1412133', 'Siennica', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                   'miński', 'powiat')
    MAZOWIECKIE_MINSKI_STANISLAWOW_MIEJSKO_WIEJSKA = ('1412143', 'Stanisławów', GminaType.MIEJSKO_WIEJSKA,
                                                      'mazowieckie', 'miński', 'powiat')
    MAZOWIECKIE_MINSKI_SULEJOWEK_MIEJSKA = ('1412151', 'Sulejówek', GminaType.MIEJSKA, 'mazowieckie', 'miński',
                                            'powiat')
    MAZOWIECKIE_MLAWSKI_MLAWA_MIEJSKA = ('1413011', 'Mława', GminaType.MIEJSKA, 'mazowieckie', 'mławski', 'powiat')
    MAZOWIECKIE_MLAWSKI_DZIERZGOWO_WIEJSKA = ('1413022', 'Dzierzgowo', GminaType.WIEJSKA, 'mazowieckie', 'mławski',
                                              'powiat')
    MAZOWIECKIE_MLAWSKI_LIPOWIEC_KOSCIELNY_WIEJSKA = ('1413032', 'Lipowiec Kościelny', GminaType.WIEJSKA, 'mazowieckie',
                                                      'mławski', 'powiat')
    MAZOWIECKIE_MLAWSKI_RADZANOW_WIEJSKA = ('1413042', 'Radzanów', GminaType.WIEJSKA, 'mazowieckie', 'mławski',
                                            'powiat')
    MAZOWIECKIE_MLAWSKI_STRZEGOWO_WIEJSKA = ('1413052', 'Strzegowo', GminaType.WIEJSKA, 'mazowieckie', 'mławski',
                                             'powiat')
    MAZOWIECKIE_MLAWSKI_STUPSK_WIEJSKA = ('1413062', 'Stupsk', GminaType.WIEJSKA, 'mazowieckie', 'mławski', 'powiat')
    MAZOWIECKIE_MLAWSKI_SZRENSK_WIEJSKA = ('1413072', 'Szreńsk', GminaType.WIEJSKA, 'mazowieckie', 'mławski', 'powiat')
    MAZOWIECKIE_MLAWSKI_SZYDLOWO_WIEJSKA = ('1413082', 'Szydłowo', GminaType.WIEJSKA, 'mazowieckie', 'mławski',
                                            'powiat')
    MAZOWIECKIE_MLAWSKI_WIECZFNIA_KOSCIELNA_WIEJSKA = ('1413092', 'Wieczfnia Kościelna', GminaType.WIEJSKA,
                                                       'mazowieckie', 'mławski', 'powiat')
    MAZOWIECKIE_MLAWSKI_WISNIEWO_WIEJSKA = ('1413102', 'Wiśniewo', GminaType.WIEJSKA, 'mazowieckie', 'mławski',
                                            'powiat')
    MAZOWIECKIE_NOWODWORSKI_NOWY_DWOR_MAZOWIECKI_MIEJSKA = ('1414011', 'Nowy Dwór Mazowiecki', GminaType.MIEJSKA,
                                                            'mazowieckie', 'nowodworski', 'powiat')
    MAZOWIECKIE_NOWODWORSKI_CZOSNOW_WIEJSKA = ('1414022', 'Czosnów', GminaType.WIEJSKA, 'mazowieckie', 'nowodworski',
                                               'powiat')
    MAZOWIECKIE_NOWODWORSKI_LEONCIN_WIEJSKA = ('1414032', 'Leoncin', GminaType.WIEJSKA, 'mazowieckie', 'nowodworski',
                                               'powiat')
    MAZOWIECKIE_NOWODWORSKI_NASIELSK_MIEJSKO_WIEJSKA = ('1414043', 'Nasielsk', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                        'nowodworski', 'powiat')
    MAZOWIECKIE_NOWODWORSKI_POMIECHOWEK_WIEJSKA = ('1414052', 'Pomiechówek', GminaType.WIEJSKA, 'mazowieckie',
                                                   'nowodworski', 'powiat')
    MAZOWIECKIE_NOWODWORSKI_ZAKROCZYM_MIEJSKO_WIEJSKA = ('1414063', 'Zakroczym', GminaType.MIEJSKO_WIEJSKA,
                                                         'mazowieckie', 'nowodworski', 'powiat')
    MAZOWIECKIE_OSTROLECKI_BARANOWO_WIEJSKA = ('1415012', 'Baranowo', GminaType.WIEJSKA, 'mazowieckie', 'ostrołęcki',
                                               'powiat')
    MAZOWIECKIE_OSTROLECKI_CZARNIA_WIEJSKA = ('1415022', 'Czarnia', GminaType.WIEJSKA, 'mazowieckie', 'ostrołęcki',
                                              'powiat')
    MAZOWIECKIE_OSTROLECKI_CZERWIN_WIEJSKA = ('1415032', 'Czerwin', GminaType.WIEJSKA, 'mazowieckie', 'ostrołęcki',
                                              'powiat')
    MAZOWIECKIE_OSTROLECKI_GOWOROWO_WIEJSKA = ('1415042', 'Goworowo', GminaType.WIEJSKA, 'mazowieckie', 'ostrołęcki',
                                               'powiat')
    MAZOWIECKIE_OSTROLECKI_KADZIDLO_WIEJSKA = ('1415052', 'Kadzidło', GminaType.WIEJSKA, 'mazowieckie', 'ostrołęcki',
                                               'powiat')
    MAZOWIECKIE_OSTROLECKI_LELIS_WIEJSKA = ('1415062', 'Lelis', GminaType.WIEJSKA, 'mazowieckie', 'ostrołęcki',
                                            'powiat')
    MAZOWIECKIE_OSTROLECKI_LYSE_WIEJSKA = ('1415072', 'Łyse', GminaType.WIEJSKA, 'mazowieckie', 'ostrołęcki', 'powiat')
    MAZOWIECKIE_OSTROLECKI_MYSZYNIEC_MIEJSKO_WIEJSKA = ('1415083', 'Myszyniec', GminaType.MIEJSKO_WIEJSKA,
                                                        'mazowieckie', 'ostrołęcki', 'powiat')
    MAZOWIECKIE_OSTROLECKI_OLSZEWO_BORKI_WIEJSKA = ('1415092', 'Olszewo-Borki', GminaType.WIEJSKA, 'mazowieckie',
                                                    'ostrołęcki', 'powiat')
    MAZOWIECKIE_OSTROLECKI_RZEKUN_WIEJSKA = ('1415102', 'Rzekuń', GminaType.WIEJSKA, 'mazowieckie', 'ostrołęcki',
                                             'powiat')
    MAZOWIECKIE_OSTROLECKI_TROSZYN_WIEJSKA = ('1415112', 'Troszyn', GminaType.WIEJSKA, 'mazowieckie', 'ostrołęcki',
                                              'powiat')
    MAZOWIECKIE_OSTROWSKI_OSTROW_MAZOWIECKA_MIEJSKA = ('1416011', 'Ostrów Mazowiecka', GminaType.MIEJSKA, 'mazowieckie',
                                                       'ostrowski', 'powiat')
    MAZOWIECKIE_OSTROWSKI_ANDRZEJEWO_WIEJSKA = ('1416022', 'Andrzejewo', GminaType.WIEJSKA, 'mazowieckie', 'ostrowski',
                                                'powiat')
    MAZOWIECKIE_OSTROWSKI_BOGUTY_PIANKI_WIEJSKA = ('1416032', 'Boguty-Pianki', GminaType.WIEJSKA, 'mazowieckie',
                                                   'ostrowski', 'powiat')
    MAZOWIECKIE_OSTROWSKI_BROK_MIEJSKO_WIEJSKA = ('1416043', 'Brok', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                  'ostrowski', 'powiat')
    MAZOWIECKIE_OSTROWSKI_MALKINIA_GORNA_MIEJSKO_WIEJSKA = ('1416053', 'Małkinia Górna', GminaType.MIEJSKO_WIEJSKA,
                                                            'mazowieckie', 'ostrowski', 'powiat')
    MAZOWIECKIE_OSTROWSKI_NUR_WIEJSKA = ('1416062', 'Nur', GminaType.WIEJSKA, 'mazowieckie', 'ostrowski', 'powiat')
    MAZOWIECKIE_OSTROWSKI_OSTROW_MAZOWIECKA_WIEJSKA = ('1416072', 'Ostrów Mazowiecka', GminaType.WIEJSKA, 'mazowieckie',
                                                       'ostrowski', 'powiat')
    MAZOWIECKIE_OSTROWSKI_STARY_LUBOTYN_WIEJSKA = ('1416082', 'Stary Lubotyń', GminaType.WIEJSKA, 'mazowieckie',
                                                   'ostrowski', 'powiat')
    MAZOWIECKIE_OSTROWSKI_SZULBORZE_WIELKIE_WIEJSKA = ('1416092', 'Szulborze Wielkie', GminaType.WIEJSKA, 'mazowieckie',
                                                       'ostrowski', 'powiat')
    MAZOWIECKIE_OSTROWSKI_WASEWO_WIEJSKA = ('1416102', 'Wąsewo', GminaType.WIEJSKA, 'mazowieckie', 'ostrowski',
                                            'powiat')
    MAZOWIECKIE_OSTROWSKI_ZAREBY_KOSCIELNE_WIEJSKA = ('1416112', 'Zaręby Kościelne', GminaType.WIEJSKA, 'mazowieckie',
                                                      'ostrowski', 'powiat')
    MAZOWIECKIE_OTWOCKI_JOZEFOW_MIEJSKA = ('1417011', 'Józefów', GminaType.MIEJSKA, 'mazowieckie', 'otwocki', 'powiat')
    MAZOWIECKIE_OTWOCKI_OTWOCK_MIEJSKA = ('1417021', 'Otwock', GminaType.MIEJSKA, 'mazowieckie', 'otwocki', 'powiat')
    MAZOWIECKIE_OTWOCKI_CELESTYNOW_WIEJSKA = ('1417032', 'Celestynów', GminaType.WIEJSKA, 'mazowieckie', 'otwocki',
                                              'powiat')
    MAZOWIECKIE_OTWOCKI_KARCZEW_MIEJSKO_WIEJSKA = ('1417043', 'Karczew', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                   'otwocki', 'powiat')
    MAZOWIECKIE_OTWOCKI_KOLBIEL_WIEJSKA = ('1417052', 'Kołbiel', GminaType.WIEJSKA, 'mazowieckie', 'otwocki', 'powiat')
    MAZOWIECKIE_OTWOCKI_OSIECK_MIEJSKO_WIEJSKA = ('1417063', 'Osieck', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                  'otwocki', 'powiat')
    MAZOWIECKIE_OTWOCKI_SOBIENIE_JEZIORY_WIEJSKA = ('1417072', 'Sobienie-Jeziory', GminaType.WIEJSKA, 'mazowieckie',
                                                    'otwocki', 'powiat')
    MAZOWIECKIE_OTWOCKI_WIAZOWNA_WIEJSKA = ('1417082', 'Wiązowna', GminaType.WIEJSKA, 'mazowieckie', 'otwocki',
                                            'powiat')
    MAZOWIECKIE_PIASECZYNSKI_GORA_KALWARIA_MIEJSKO_WIEJSKA = ('1418013', 'Góra Kalwaria', GminaType.MIEJSKO_WIEJSKA,
                                                              'mazowieckie', 'piaseczyński', 'powiat')
    MAZOWIECKIE_PIASECZYNSKI_KONSTANCIN_JEZIORNA_MIEJSKO_WIEJSKA = ('1418023', 'Konstancin-Jeziorna',
                                                                    GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                                    'piaseczyński', 'powiat')
    MAZOWIECKIE_PIASECZYNSKI_LESZNOWOLA_WIEJSKA = ('1418032', 'Lesznowola', GminaType.WIEJSKA, 'mazowieckie',
                                                   'piaseczyński', 'powiat')
    MAZOWIECKIE_PIASECZYNSKI_PIASECZNO_MIEJSKO_WIEJSKA = ('1418043', 'Piaseczno', GminaType.MIEJSKO_WIEJSKA,
                                                          'mazowieckie', 'piaseczyński', 'powiat')
    MAZOWIECKIE_PIASECZYNSKI_PRAZMOW_WIEJSKA = ('1418052', 'Prażmów', GminaType.WIEJSKA, 'mazowieckie', 'piaseczyński',
                                                'powiat')
    MAZOWIECKIE_PIASECZYNSKI_TARCZYN_MIEJSKO_WIEJSKA = ('1418063', 'Tarczyn', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                        'piaseczyński', 'powiat')
    MAZOWIECKIE_PLOCKI_BIELSK_WIEJSKA = ('1419012', 'Bielsk', GminaType.WIEJSKA, 'mazowieckie', 'płocki', 'powiat')
    MAZOWIECKIE_PLOCKI_BODZANOW_MIEJSKO_WIEJSKA = ('1419023', 'Bodzanów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                   'płocki', 'powiat')
    MAZOWIECKIE_PLOCKI_BRUDZEN_DUZY_WIEJSKA = ('1419032', 'Brudzeń Duży', GminaType.WIEJSKA, 'mazowieckie', 'płocki',
                                               'powiat')
    MAZOWIECKIE_PLOCKI_BULKOWO_WIEJSKA = ('1419042', 'Bulkowo', GminaType.WIEJSKA, 'mazowieckie', 'płocki', 'powiat')
    MAZOWIECKIE_PLOCKI_DROBIN_MIEJSKO_WIEJSKA = ('1419053', 'Drobin', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                 'płocki', 'powiat')
    MAZOWIECKIE_PLOCKI_GABIN_MIEJSKO_WIEJSKA = ('1419063', 'Gąbin', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie', 'płocki',
                                                'powiat')
    MAZOWIECKIE_PLOCKI_LACK_WIEJSKA = ('1419072', 'Łąck', GminaType.WIEJSKA, 'mazowieckie', 'płocki', 'powiat')
    MAZOWIECKIE_PLOCKI_MALA_WIES_WIEJSKA = ('1419082', 'Mała Wieś', GminaType.WIEJSKA, 'mazowieckie', 'płocki',
                                            'powiat')
    MAZOWIECKIE_PLOCKI_NOWY_DUNINOW_WIEJSKA = ('1419092', 'Nowy Duninów', GminaType.WIEJSKA, 'mazowieckie', 'płocki',
                                               'powiat')
    MAZOWIECKIE_PLOCKI_RADZANOWO_WIEJSKA = ('1419102', 'Radzanowo', GminaType.WIEJSKA, 'mazowieckie', 'płocki',
                                            'powiat')
    MAZOWIECKIE_PLOCKI_SLUBICE_WIEJSKA = ('1419112', 'Słubice', GminaType.WIEJSKA, 'mazowieckie', 'płocki', 'powiat')
    MAZOWIECKIE_PLOCKI_SLUPNO_WIEJSKA = ('1419122', 'Słupno', GminaType.WIEJSKA, 'mazowieckie', 'płocki', 'powiat')
    MAZOWIECKIE_PLOCKI_STARA_BIALA_WIEJSKA = ('1419132', 'Stara Biała', GminaType.WIEJSKA, 'mazowieckie', 'płocki',
                                              'powiat')
    MAZOWIECKIE_PLOCKI_STAROZREBY_MIEJSKO_WIEJSKA = ('1419143', 'Staroźreby', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                     'płocki', 'powiat')
    MAZOWIECKIE_PLOCKI_WYSZOGROD_MIEJSKO_WIEJSKA = ('1419153', 'Wyszogród', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                    'płocki', 'powiat')
    MAZOWIECKIE_PLONSKI_PLONSK_MIEJSKA = ('1420011', 'Płońsk', GminaType.MIEJSKA, 'mazowieckie', 'płoński', 'powiat')
    MAZOWIECKIE_PLONSKI_RACIAZ_MIEJSKA = ('1420021', 'Raciąż', GminaType.MIEJSKA, 'mazowieckie', 'płoński', 'powiat')
    MAZOWIECKIE_PLONSKI_BABOSZEWO_WIEJSKA = ('1420032', 'Baboszewo', GminaType.WIEJSKA, 'mazowieckie', 'płoński',
                                             'powiat')
    MAZOWIECKIE_PLONSKI_CZERWINSK_NAD_WISLA_MIEJSKO_WIEJSKA = ('1420043', 'Czerwińsk nad Wisłą',
                                                               GminaType.MIEJSKO_WIEJSKA, 'mazowieckie', 'płoński',
                                                               'powiat')
    MAZOWIECKIE_PLONSKI_DZIERZAZNIA_WIEJSKA = ('1420052', 'Dzierzążnia', GminaType.WIEJSKA, 'mazowieckie', 'płoński',
                                               'powiat')
    MAZOWIECKIE_PLONSKI_JONIEC_WIEJSKA = ('1420062', 'Joniec', GminaType.WIEJSKA, 'mazowieckie', 'płoński', 'powiat')
    MAZOWIECKIE_PLONSKI_NARUSZEWO_WIEJSKA = ('1420072', 'Naruszewo', GminaType.WIEJSKA, 'mazowieckie', 'płoński',
                                             'powiat')
    MAZOWIECKIE_PLONSKI_NOWE_MIASTO_MIEJSKO_WIEJSKA = ('1420083', 'Nowe Miasto', GminaType.MIEJSKO_WIEJSKA,
                                                       'mazowieckie', 'płoński', 'powiat')
    MAZOWIECKIE_PLONSKI_PLONSK_WIEJSKA = ('1420092', 'Płońsk', GminaType.WIEJSKA, 'mazowieckie', 'płoński', 'powiat')
    MAZOWIECKIE_PLONSKI_RACIAZ_WIEJSKA = ('1420102', 'Raciąż', GminaType.WIEJSKA, 'mazowieckie', 'płoński', 'powiat')
    MAZOWIECKIE_PLONSKI_SOCHOCIN_MIEJSKO_WIEJSKA = ('1420113', 'Sochocin', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                    'płoński', 'powiat')
    MAZOWIECKIE_PLONSKI_ZALUSKI_WIEJSKA = ('1420122', 'Załuski', GminaType.WIEJSKA, 'mazowieckie', 'płoński', 'powiat')
    MAZOWIECKIE_PRUSZKOWSKI_PIASTOW_MIEJSKA = ('1421011', 'Piastów', GminaType.MIEJSKA, 'mazowieckie', 'pruszkowski',
                                               'powiat')
    MAZOWIECKIE_PRUSZKOWSKI_PRUSZKOW_MIEJSKA = ('1421021', 'Pruszków', GminaType.MIEJSKA, 'mazowieckie', 'pruszkowski',
                                                'powiat')
    MAZOWIECKIE_PRUSZKOWSKI_BRWINOW_MIEJSKO_WIEJSKA = ('1421033', 'Brwinów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                       'pruszkowski', 'powiat')
    MAZOWIECKIE_PRUSZKOWSKI_MICHALOWICE_WIEJSKA = ('1421042', 'Michałowice', GminaType.WIEJSKA, 'mazowieckie',
                                                   'pruszkowski', 'powiat')
    MAZOWIECKIE_PRUSZKOWSKI_NADARZYN_WIEJSKA = ('1421052', 'Nadarzyn', GminaType.WIEJSKA, 'mazowieckie', 'pruszkowski',
                                                'powiat')
    MAZOWIECKIE_PRUSZKOWSKI_RASZYN_WIEJSKA = ('1421062', 'Raszyn', GminaType.WIEJSKA, 'mazowieckie', 'pruszkowski',
                                              'powiat')
    MAZOWIECKIE_PRZASNYSKI_PRZASNYSZ_MIEJSKA = ('1422011', 'Przasnysz', GminaType.MIEJSKA, 'mazowieckie', 'przasnyski',
                                                'powiat')
    MAZOWIECKIE_PRZASNYSKI_CHORZELE_MIEJSKO_WIEJSKA = ('1422023', 'Chorzele', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                       'przasnyski', 'powiat')
    MAZOWIECKIE_PRZASNYSKI_CZERNICE_BOROWE_WIEJSKA = ('1422032', 'Czernice Borowe', GminaType.WIEJSKA, 'mazowieckie',
                                                      'przasnyski', 'powiat')
    MAZOWIECKIE_PRZASNYSKI_JEDNOROZEC_WIEJSKA = ('1422042', 'Jednorożec', GminaType.WIEJSKA, 'mazowieckie',
                                                 'przasnyski', 'powiat')
    MAZOWIECKIE_PRZASNYSKI_KRASNE_WIEJSKA = ('1422052', 'Krasne', GminaType.WIEJSKA, 'mazowieckie', 'przasnyski',
                                             'powiat')
    MAZOWIECKIE_PRZASNYSKI_KRZYNOWLOGA_MALA_WIEJSKA = ('1422062', 'Krzynowłoga Mała', GminaType.WIEJSKA, 'mazowieckie',
                                                       'przasnyski', 'powiat')
    MAZOWIECKIE_PRZASNYSKI_PRZASNYSZ_WIEJSKA = ('1422072', 'Przasnysz', GminaType.WIEJSKA, 'mazowieckie', 'przasnyski',
                                                'powiat')
    MAZOWIECKIE_PRZYSUSKI_BORKOWICE_WIEJSKA = ('1423012', 'Borkowice', GminaType.WIEJSKA, 'mazowieckie', 'przysuski',
                                               'powiat')
    MAZOWIECKIE_PRZYSUSKI_GIELNIOW_MIEJSKO_WIEJSKA = ('1423023', 'Gielniów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                      'przysuski', 'powiat')
    MAZOWIECKIE_PRZYSUSKI_KLWOW_WIEJSKA = ('1423032', 'Klwów', GminaType.WIEJSKA, 'mazowieckie', 'przysuski', 'powiat')
    MAZOWIECKIE_PRZYSUSKI_ODRZYWOL_MIEJSKO_WIEJSKA = ('1423043', 'Odrzywół', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                      'przysuski', 'powiat')
    MAZOWIECKIE_PRZYSUSKI_POTWOROW_WIEJSKA = ('1423052', 'Potworów', GminaType.WIEJSKA, 'mazowieckie', 'przysuski',
                                              'powiat')
    MAZOWIECKIE_PRZYSUSKI_PRZYSUCHA_MIEJSKO_WIEJSKA = ('1423063', 'Przysucha', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                       'przysuski', 'powiat')
    MAZOWIECKIE_PRZYSUSKI_RUSINOW_WIEJSKA = ('1423072', 'Rusinów', GminaType.WIEJSKA, 'mazowieckie', 'przysuski',
                                             'powiat')
    MAZOWIECKIE_PRZYSUSKI_WIENIAWA_WIEJSKA = ('1423082', 'Wieniawa', GminaType.WIEJSKA, 'mazowieckie', 'przysuski',
                                              'powiat')
    MAZOWIECKIE_PULTUSKI_GZY_WIEJSKA = ('1424012', 'Gzy', GminaType.WIEJSKA, 'mazowieckie', 'pułtuski', 'powiat')
    MAZOWIECKIE_PULTUSKI_OBRYTE_WIEJSKA = ('1424022', 'Obryte', GminaType.WIEJSKA, 'mazowieckie', 'pułtuski', 'powiat')
    MAZOWIECKIE_PULTUSKI_POKRZYWNICA_WIEJSKA = ('1424032', 'Pokrzywnica', GminaType.WIEJSKA, 'mazowieckie', 'pułtuski',
                                                'powiat')
    MAZOWIECKIE_PULTUSKI_PULTUSK_MIEJSKO_WIEJSKA = ('1424043', 'Pułtusk', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                    'pułtuski', 'powiat')
    MAZOWIECKIE_PULTUSKI_SWIERCZE_WIEJSKA = ('1424052', 'Świercze', GminaType.WIEJSKA, 'mazowieckie', 'pułtuski',
                                             'powiat')
    MAZOWIECKIE_PULTUSKI_WINNICA_WIEJSKA = ('1424062', 'Winnica', GminaType.WIEJSKA, 'mazowieckie', 'pułtuski',
                                            'powiat')
    MAZOWIECKIE_PULTUSKI_ZATORY_WIEJSKA = ('1424072', 'Zatory', GminaType.WIEJSKA, 'mazowieckie', 'pułtuski', 'powiat')
    MAZOWIECKIE_RADOMSKI_PIONKI_MIEJSKA = ('1425011', 'Pionki', GminaType.MIEJSKA, 'mazowieckie', 'radomski', 'powiat')
    MAZOWIECKIE_RADOMSKI_GOZD_WIEJSKA = ('1425022', 'Gózd', GminaType.WIEJSKA, 'mazowieckie', 'radomski', 'powiat')
    MAZOWIECKIE_RADOMSKI_ILZA_MIEJSKO_WIEJSKA = ('1425033', 'Iłża', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                 'radomski', 'powiat')
    MAZOWIECKIE_RADOMSKI_JASTRZEBIA_WIEJSKA = ('1425042', 'Jastrzębia', GminaType.WIEJSKA, 'mazowieckie', 'radomski',
                                               'powiat')
    MAZOWIECKIE_RADOMSKI_JEDLINSK_WIEJSKA = ('1425052', 'Jedlińsk', GminaType.WIEJSKA, 'mazowieckie', 'radomski',
                                             'powiat')
    MAZOWIECKIE_RADOMSKI_JEDLNIA_LETNISKO_MIEJSKO_WIEJSKA = ('1425063', 'Jedlnia-Letnisko', GminaType.MIEJSKO_WIEJSKA,
                                                             'mazowieckie', 'radomski', 'powiat')
    MAZOWIECKIE_RADOMSKI_KOWALA_WIEJSKA = ('1425072', 'Kowala', GminaType.WIEJSKA, 'mazowieckie', 'radomski', 'powiat')
    MAZOWIECKIE_RADOMSKI_PIONKI_WIEJSKA = ('1425082', 'Pionki', GminaType.WIEJSKA, 'mazowieckie', 'radomski', 'powiat')
    MAZOWIECKIE_RADOMSKI_PRZYTYK_MIEJSKO_WIEJSKA = ('1425093', 'Przytyk', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                    'radomski', 'powiat')
    MAZOWIECKIE_RADOMSKI_SKARYSZEW_MIEJSKO_WIEJSKA = ('1425103', 'Skaryszew', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                      'radomski', 'powiat')
    MAZOWIECKIE_RADOMSKI_WIERZBICA_WIEJSKA = ('1425112', 'Wierzbica', GminaType.WIEJSKA, 'mazowieckie', 'radomski',
                                              'powiat')
    MAZOWIECKIE_RADOMSKI_WOLANOW_WIEJSKA = ('1425122', 'Wolanów', GminaType.WIEJSKA, 'mazowieckie', 'radomski',
                                            'powiat')
    MAZOWIECKIE_RADOMSKI_ZAKRZEW_WIEJSKA = ('1425132', 'Zakrzew', GminaType.WIEJSKA, 'mazowieckie', 'radomski',
                                            'powiat')
    MAZOWIECKIE_SIEDLECKI_DOMANICE_WIEJSKA = ('1426012', 'Domanice', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                              'powiat')
    MAZOWIECKIE_SIEDLECKI_KORCZEW_WIEJSKA = ('1426022', 'Korczew', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                             'powiat')
    MAZOWIECKIE_SIEDLECKI_KOTUN_WIEJSKA = ('1426032', 'Kotuń', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki', 'powiat')
    MAZOWIECKIE_SIEDLECKI_MOKOBODY_WIEJSKA = ('1426042', 'Mokobody', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                              'powiat')
    MAZOWIECKIE_SIEDLECKI_MORDY_MIEJSKO_WIEJSKA = ('1426053', 'Mordy', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                   'siedlecki', 'powiat')
    MAZOWIECKIE_SIEDLECKI_PAPROTNIA_WIEJSKA = ('1426062', 'Paprotnia', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                               'powiat')
    MAZOWIECKIE_SIEDLECKI_PRZESMYKI_WIEJSKA = ('1426072', 'Przesmyki', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                               'powiat')
    MAZOWIECKIE_SIEDLECKI_SIEDLCE_WIEJSKA = ('1426082', 'Siedlce', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                             'powiat')
    MAZOWIECKIE_SIEDLECKI_SKORZEC_WIEJSKA = ('1426092', 'Skórzec', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                             'powiat')
    MAZOWIECKIE_SIEDLECKI_SUCHOZEBRY_WIEJSKA = ('1426102', 'Suchożebry', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                                'powiat')
    MAZOWIECKIE_SIEDLECKI_WISNIEW_WIEJSKA = ('1426112', 'Wiśniew', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                             'powiat')
    MAZOWIECKIE_SIEDLECKI_WODYNIE_WIEJSKA = ('1426122', 'Wodynie', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                             'powiat')
    MAZOWIECKIE_SIEDLECKI_ZBUCZYN_WIEJSKA = ('1426132', 'Zbuczyn', GminaType.WIEJSKA, 'mazowieckie', 'siedlecki',
                                             'powiat')
    MAZOWIECKIE_SIERPECKI_SIERPC_MIEJSKA = ('1427011', 'Sierpc', GminaType.MIEJSKA, 'mazowieckie', 'sierpecki',
                                            'powiat')
    MAZOWIECKIE_SIERPECKI_GOZDOWO_WIEJSKA = ('1427022', 'Gozdowo', GminaType.WIEJSKA, 'mazowieckie', 'sierpecki',
                                             'powiat')
    MAZOWIECKIE_SIERPECKI_MOCHOWO_WIEJSKA = ('1427032', 'Mochowo', GminaType.WIEJSKA, 'mazowieckie', 'sierpecki',
                                             'powiat')
    MAZOWIECKIE_SIERPECKI_ROSCISZEWO_WIEJSKA = ('1427042', 'Rościszewo', GminaType.WIEJSKA, 'mazowieckie', 'sierpecki',
                                                'powiat')
    MAZOWIECKIE_SIERPECKI_SIERPC_WIEJSKA = ('1427052', 'Sierpc', GminaType.WIEJSKA, 'mazowieckie', 'sierpecki',
                                            'powiat')
    MAZOWIECKIE_SIERPECKI_SZCZUTOWO_WIEJSKA = ('1427062', 'Szczutowo', GminaType.WIEJSKA, 'mazowieckie', 'sierpecki',
                                               'powiat')
    MAZOWIECKIE_SIERPECKI_ZAWIDZ_WIEJSKA = ('1427072', 'Zawidz', GminaType.WIEJSKA, 'mazowieckie', 'sierpecki',
                                            'powiat')
    MAZOWIECKIE_SOCHACZEWSKI_SOCHACZEW_MIEJSKA = ('1428011', 'Sochaczew', GminaType.MIEJSKA, 'mazowieckie',
                                                  'sochaczewski', 'powiat')
    MAZOWIECKIE_SOCHACZEWSKI_BROCHOW_WIEJSKA = ('1428022', 'Brochów', GminaType.WIEJSKA, 'mazowieckie', 'sochaczewski',
                                                'powiat')
    MAZOWIECKIE_SOCHACZEWSKI_ILOW_WIEJSKA = ('1428032', 'Iłów', GminaType.WIEJSKA, 'mazowieckie', 'sochaczewski',
                                             'powiat')
    MAZOWIECKIE_SOCHACZEWSKI_MLODZIESZYN_WIEJSKA = ('1428042', 'Młodzieszyn', GminaType.WIEJSKA, 'mazowieckie',
                                                    'sochaczewski', 'powiat')
    MAZOWIECKIE_SOCHACZEWSKI_NOWA_SUCHA_WIEJSKA = ('1428052', 'Nowa Sucha', GminaType.WIEJSKA, 'mazowieckie',
                                                   'sochaczewski', 'powiat')
    MAZOWIECKIE_SOCHACZEWSKI_RYBNO_WIEJSKA = ('1428062', 'Rybno', GminaType.WIEJSKA, 'mazowieckie', 'sochaczewski',
                                              'powiat')
    MAZOWIECKIE_SOCHACZEWSKI_SOCHACZEW_WIEJSKA = ('1428072', 'Sochaczew', GminaType.WIEJSKA, 'mazowieckie',
                                                  'sochaczewski', 'powiat')
    MAZOWIECKIE_SOCHACZEWSKI_TERESIN_WIEJSKA = ('1428082', 'Teresin', GminaType.WIEJSKA, 'mazowieckie', 'sochaczewski',
                                                'powiat')
    MAZOWIECKIE_SOKOLOWSKI_SOKOLOW_PODLASKI_MIEJSKA = ('1429011', 'Sokołów Podlaski', GminaType.MIEJSKA, 'mazowieckie',
                                                       'sokołowski', 'powiat')
    MAZOWIECKIE_SOKOLOWSKI_BIELANY_WIEJSKA = ('1429022', 'Bielany', GminaType.WIEJSKA, 'mazowieckie', 'sokołowski',
                                              'powiat')
    MAZOWIECKIE_SOKOLOWSKI_CERANOW_WIEJSKA = ('1429032', 'Ceranów', GminaType.WIEJSKA, 'mazowieckie', 'sokołowski',
                                              'powiat')
    MAZOWIECKIE_SOKOLOWSKI_JABLONNA_LACKA_WIEJSKA = ('1429042', 'Jabłonna Lacka', GminaType.WIEJSKA, 'mazowieckie',
                                                     'sokołowski', 'powiat')
    MAZOWIECKIE_SOKOLOWSKI_KOSOW_LACKI_MIEJSKO_WIEJSKA = ('1429053', 'Kosów Lacki', GminaType.MIEJSKO_WIEJSKA,
                                                          'mazowieckie', 'sokołowski', 'powiat')
    MAZOWIECKIE_SOKOLOWSKI_REPKI_WIEJSKA = ('1429062', 'Repki', GminaType.WIEJSKA, 'mazowieckie', 'sokołowski',
                                            'powiat')
    MAZOWIECKIE_SOKOLOWSKI_SABNIE_WIEJSKA = ('1429072', 'Sabnie', GminaType.WIEJSKA, 'mazowieckie', 'sokołowski',
                                             'powiat')
    MAZOWIECKIE_SOKOLOWSKI_SOKOLOW_PODLASKI_WIEJSKA = ('1429082', 'Sokołów Podlaski', GminaType.WIEJSKA, 'mazowieckie',
                                                       'sokołowski', 'powiat')
    MAZOWIECKIE_SOKOLOWSKI_STERDYN_WIEJSKA = ('1429092', 'Sterdyń', GminaType.WIEJSKA, 'mazowieckie', 'sokołowski',
                                              'powiat')
    MAZOWIECKIE_SZYDLOWIECKI_CHLEWISKA_WIEJSKA = ('1430012', 'Chlewiska', GminaType.WIEJSKA, 'mazowieckie',
                                                  'szydłowiecki', 'powiat')
    MAZOWIECKIE_SZYDLOWIECKI_JASTRZAB_MIEJSKO_WIEJSKA = ('1430023', 'Jastrząb', GminaType.MIEJSKO_WIEJSKA,
                                                         'mazowieckie', 'szydłowiecki', 'powiat')
    MAZOWIECKIE_SZYDLOWIECKI_MIROW_WIEJSKA = ('1430032', 'Mirów', GminaType.WIEJSKA, 'mazowieckie', 'szydłowiecki',
                                              'powiat')
    MAZOWIECKIE_SZYDLOWIECKI_ORONSKO_WIEJSKA = ('1430042', 'Orońsko', GminaType.WIEJSKA, 'mazowieckie', 'szydłowiecki',
                                                'powiat')
    MAZOWIECKIE_SZYDLOWIECKI_SZYDLOWIEC_MIEJSKO_WIEJSKA = ('1430053', 'Szydłowiec', GminaType.MIEJSKO_WIEJSKA,
                                                           'mazowieckie', 'szydłowiecki', 'powiat')
    MAZOWIECKIE_WARSZAWSKI_ZACHODNI_BLONIE_MIEJSKO_WIEJSKA = ('1432013', 'Błonie', GminaType.MIEJSKO_WIEJSKA,
                                                              'mazowieckie', 'warszawski zachodni', 'powiat')
    MAZOWIECKIE_WARSZAWSKI_ZACHODNI_IZABELIN_WIEJSKA = ('1432022', 'Izabelin', GminaType.WIEJSKA, 'mazowieckie',
                                                        'warszawski zachodni', 'powiat')
    MAZOWIECKIE_WARSZAWSKI_ZACHODNI_KAMPINOS_WIEJSKA = ('1432032', 'Kampinos', GminaType.WIEJSKA, 'mazowieckie',
                                                        'warszawski zachodni', 'powiat')
    MAZOWIECKIE_WARSZAWSKI_ZACHODNI_LESZNO_WIEJSKA = ('1432042', 'Leszno', GminaType.WIEJSKA, 'mazowieckie',
                                                      'warszawski zachodni', 'powiat')
    MAZOWIECKIE_WARSZAWSKI_ZACHODNI_LOMIANKI_MIEJSKO_WIEJSKA = ('1432053', 'Łomianki', GminaType.MIEJSKO_WIEJSKA,
                                                                'mazowieckie', 'warszawski zachodni', 'powiat')
    MAZOWIECKIE_WARSZAWSKI_ZACHODNI_OZAROW_MAZOWIECKI_MIEJSKO_WIEJSKA = ('1432063', 'Ożarów Mazowiecki',
                                                                         GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                                         'warszawski zachodni', 'powiat')
    MAZOWIECKIE_WARSZAWSKI_ZACHODNI_STARE_BABICE_WIEJSKA = ('1432072', 'Stare Babice', GminaType.WIEJSKA, 'mazowieckie',
                                                            'warszawski zachodni', 'powiat')
    MAZOWIECKIE_WEGROWSKI_WEGROW_MIEJSKA = ('1433011', 'Węgrów', GminaType.MIEJSKA, 'mazowieckie', 'węgrowski',
                                            'powiat')
    MAZOWIECKIE_WEGROWSKI_GREBKOW_WIEJSKA = ('1433022', 'Grębków', GminaType.WIEJSKA, 'mazowieckie', 'węgrowski',
                                             'powiat')
    MAZOWIECKIE_WEGROWSKI_KORYTNICA_WIEJSKA = ('1433032', 'Korytnica', GminaType.WIEJSKA, 'mazowieckie', 'węgrowski',
                                               'powiat')
    MAZOWIECKIE_WEGROWSKI_LIW_WIEJSKA = ('1433042', 'Liw', GminaType.WIEJSKA, 'mazowieckie', 'węgrowski', 'powiat')
    MAZOWIECKIE_WEGROWSKI_LOCHOW_MIEJSKO_WIEJSKA = ('1433053', 'Łochów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                    'węgrowski', 'powiat')
    MAZOWIECKIE_WEGROWSKI_MIEDZNA_WIEJSKA = ('1433062', 'Miedzna', GminaType.WIEJSKA, 'mazowieckie', 'węgrowski',
                                             'powiat')
    MAZOWIECKIE_WEGROWSKI_SADOWNE_WIEJSKA = ('1433072', 'Sadowne', GminaType.WIEJSKA, 'mazowieckie', 'węgrowski',
                                             'powiat')
    MAZOWIECKIE_WEGROWSKI_STOCZEK_WIEJSKA = ('1433082', 'Stoczek', GminaType.WIEJSKA, 'mazowieckie', 'węgrowski',
                                             'powiat')
    MAZOWIECKIE_WEGROWSKI_WIERZBNO_WIEJSKA = ('1433092', 'Wierzbno', GminaType.WIEJSKA, 'mazowieckie', 'węgrowski',
                                              'powiat')
    MAZOWIECKIE_WOLOMINSKI_KOBYLKA_MIEJSKA = ('1434011', 'Kobyłka', GminaType.MIEJSKA, 'mazowieckie', 'wołomiński',
                                              'powiat')
    MAZOWIECKIE_WOLOMINSKI_MARKI_MIEJSKA = ('1434021', 'Marki', GminaType.MIEJSKA, 'mazowieckie', 'wołomiński',
                                            'powiat')
    MAZOWIECKIE_WOLOMINSKI_ZABKI_MIEJSKA = ('1434031', 'Ząbki', GminaType.MIEJSKA, 'mazowieckie', 'wołomiński',
                                            'powiat')
    MAZOWIECKIE_WOLOMINSKI_ZIELONKA_MIEJSKA = ('1434041', 'Zielonka', GminaType.MIEJSKA, 'mazowieckie', 'wołomiński',
                                               'powiat')
    MAZOWIECKIE_WOLOMINSKI_DABROWKA_WIEJSKA = ('1434052', 'Dąbrówka', GminaType.WIEJSKA, 'mazowieckie', 'wołomiński',
                                               'powiat')
    MAZOWIECKIE_WOLOMINSKI_JADOW_MIEJSKO_WIEJSKA = ('1434063', 'Jadów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                    'wołomiński', 'powiat')
    MAZOWIECKIE_WOLOMINSKI_KLEMBOW_WIEJSKA = ('1434072', 'Klembów', GminaType.WIEJSKA, 'mazowieckie', 'wołomiński',
                                              'powiat')
    MAZOWIECKIE_WOLOMINSKI_POSWIETNE_WIEJSKA = ('1434082', 'Poświętne', GminaType.WIEJSKA, 'mazowieckie', 'wołomiński',
                                                'powiat')
    MAZOWIECKIE_WOLOMINSKI_RADZYMIN_MIEJSKO_WIEJSKA = ('1434093', 'Radzymin', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                       'wołomiński', 'powiat')
    MAZOWIECKIE_WOLOMINSKI_STRACHOWKA_WIEJSKA = ('1434102', 'Strachówka', GminaType.WIEJSKA, 'mazowieckie',
                                                 'wołomiński', 'powiat')
    MAZOWIECKIE_WOLOMINSKI_TLUSZCZ_MIEJSKO_WIEJSKA = ('1434113', 'Tłuszcz', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                      'wołomiński', 'powiat')
    MAZOWIECKIE_WOLOMINSKI_WOLOMIN_MIEJSKO_WIEJSKA = ('1434123', 'Wołomin', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                      'wołomiński', 'powiat')
    MAZOWIECKIE_WYSZKOWSKI_BRANSZCZYK_WIEJSKA = ('1435012', 'Brańszczyk', GminaType.WIEJSKA, 'mazowieckie',
                                                 'wyszkowski', 'powiat')
    MAZOWIECKIE_WYSZKOWSKI_DLUGOSIODLO_WIEJSKA = ('1435022', 'Długosiodło', GminaType.WIEJSKA, 'mazowieckie',
                                                  'wyszkowski', 'powiat')
    MAZOWIECKIE_WYSZKOWSKI_RZASNIK_WIEJSKA = ('1435032', 'Rząśnik', GminaType.WIEJSKA, 'mazowieckie', 'wyszkowski',
                                              'powiat')
    MAZOWIECKIE_WYSZKOWSKI_SOMIANKA_WIEJSKA = ('1435042', 'Somianka', GminaType.WIEJSKA, 'mazowieckie', 'wyszkowski',
                                               'powiat')
    MAZOWIECKIE_WYSZKOWSKI_WYSZKOW_MIEJSKO_WIEJSKA = ('1435053', 'Wyszków', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                      'wyszkowski', 'powiat')
    MAZOWIECKIE_WYSZKOWSKI_ZABRODZIE_WIEJSKA = ('1435062', 'Zabrodzie', GminaType.WIEJSKA, 'mazowieckie', 'wyszkowski',
                                                'powiat')
    MAZOWIECKIE_ZWOLENSKI_KAZANOW_MIEJSKO_WIEJSKA = ('1436013', 'Kazanów', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                     'zwoleński', 'powiat')
    MAZOWIECKIE_ZWOLENSKI_POLICZNA_WIEJSKA = ('1436022', 'Policzna', GminaType.WIEJSKA, 'mazowieckie', 'zwoleński',
                                              'powiat')
    MAZOWIECKIE_ZWOLENSKI_PRZYLEK_WIEJSKA = ('1436032', 'Przyłęk', GminaType.WIEJSKA, 'mazowieckie', 'zwoleński',
                                             'powiat')
    MAZOWIECKIE_ZWOLENSKI_TCZOW_WIEJSKA = ('1436042', 'Tczów', GminaType.WIEJSKA, 'mazowieckie', 'zwoleński', 'powiat')
    MAZOWIECKIE_ZWOLENSKI_ZWOLEN_MIEJSKO_WIEJSKA = ('1436053', 'Zwoleń', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                    'zwoleński', 'powiat')
    MAZOWIECKIE_ZUROMINSKI_BIEZUN_MIEJSKO_WIEJSKA = ('1437013', 'Bieżuń', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                     'żuromiński', 'powiat')
    MAZOWIECKIE_ZUROMINSKI_KUCZBORK_OSADA_WIEJSKA = ('1437022', 'Kuczbork-Osada', GminaType.WIEJSKA, 'mazowieckie',
                                                     'żuromiński', 'powiat')
    MAZOWIECKIE_ZUROMINSKI_LUBOWIDZ_MIEJSKO_WIEJSKA = ('1437033', 'Lubowidz', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                       'żuromiński', 'powiat')
    MAZOWIECKIE_ZUROMINSKI_LUTOCIN_WIEJSKA = ('1437042', 'Lutocin', GminaType.WIEJSKA, 'mazowieckie', 'żuromiński',
                                              'powiat')
    MAZOWIECKIE_ZUROMINSKI_SIEMIATKOWO_WIEJSKA = ('1437052', 'Siemiątkowo', GminaType.WIEJSKA, 'mazowieckie',
                                                  'żuromiński', 'powiat')
    MAZOWIECKIE_ZUROMINSKI_ZUROMIN_MIEJSKO_WIEJSKA = ('1437063', 'Żuromin', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                      'żuromiński', 'powiat')
    MAZOWIECKIE_ZYRARDOWSKI_ZYRARDOW_MIEJSKA = ('1438011', 'Żyrardów', GminaType.MIEJSKA, 'mazowieckie', 'żyrardowski',
                                                'powiat')
    MAZOWIECKIE_ZYRARDOWSKI_MSZCZONOW_MIEJSKO_WIEJSKA = ('1438023', 'Mszczonów', GminaType.MIEJSKO_WIEJSKA,
                                                         'mazowieckie', 'żyrardowski', 'powiat')
    MAZOWIECKIE_ZYRARDOWSKI_PUSZCZA_MARIANSKA_WIEJSKA = ('1438032', 'Puszcza Mariańska', GminaType.WIEJSKA,
                                                         'mazowieckie', 'żyrardowski', 'powiat')
    MAZOWIECKIE_ZYRARDOWSKI_RADZIEJOWICE_WIEJSKA = ('1438042', 'Radziejowice', GminaType.WIEJSKA, 'mazowieckie',
                                                    'żyrardowski', 'powiat')
    MAZOWIECKIE_ZYRARDOWSKI_WISKITKI_MIEJSKO_WIEJSKA = ('1438053', 'Wiskitki', GminaType.MIEJSKO_WIEJSKA, 'mazowieckie',
                                                        'żyrardowski', 'powiat')
    MAZOWIECKIE_OSTROLEKA_OSTROLEKA_MIEJSKA = ('1461011', 'Ostrołęka', GminaType.MIEJSKA, 'mazowieckie', 'Ostrołęka',
                                               'miasto na prawach powiatu')
    MAZOWIECKIE_PLOCK_PLOCK_MIEJSKA = ('1462011', 'Płock', GminaType.MIEJSKA, 'mazowieckie', 'Płock',
                                       'miasto na prawach powiatu')
    MAZOWIECKIE_RADOM_RADOM_MIEJSKA = ('1463011', 'Radom', GminaType.MIEJSKA, 'mazowieckie', 'Radom',
                                       'miasto na prawach powiatu')
    MAZOWIECKIE_SIEDLCE_SIEDLCE_MIEJSKA = ('1464011', 'Siedlce', GminaType.MIEJSKA, 'mazowieckie', 'Siedlce',
                                           'miasto na prawach powiatu')
    MAZOWIECKIE_WARSZAWA_WARSZAWA_MIEJSKA = ('1465011', 'Warszawa', GminaType.MIEJSKA, 'mazowieckie', 'Warszawa',
                                             'miasto stołeczne, na prawach powiatu')

    # Opolskie
    OPOLSKIE_BRZESKI_BRZEG_MIEJSKA = ('1601011', 'Brzeg', GminaType.MIEJSKA, 'opolskie', 'brzeski', 'powiat')
    OPOLSKIE_BRZESKI_SKARBIMIERZ_WIEJSKA = ('1601022', 'Skarbimierz', GminaType.WIEJSKA, 'opolskie', 'brzeski',
                                            'powiat')
    OPOLSKIE_BRZESKI_GRODKOW_MIEJSKO_WIEJSKA = ('1601033', 'Grodków', GminaType.MIEJSKO_WIEJSKA, 'opolskie', 'brzeski',
                                                'powiat')
    OPOLSKIE_BRZESKI_LEWIN_BRZESKI_MIEJSKO_WIEJSKA = ('1601043', 'Lewin Brzeski', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                      'brzeski', 'powiat')
    OPOLSKIE_BRZESKI_LUBSZA_WIEJSKA = ('1601052', 'Lubsza', GminaType.WIEJSKA, 'opolskie', 'brzeski', 'powiat')
    OPOLSKIE_BRZESKI_OLSZANKA_WIEJSKA = ('1601062', 'Olszanka', GminaType.WIEJSKA, 'opolskie', 'brzeski', 'powiat')
    OPOLSKIE_GLUBCZYCKI_BABOROW_MIEJSKO_WIEJSKA = ('1602013', 'Baborów', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                   'głubczycki', 'powiat')
    OPOLSKIE_GLUBCZYCKI_BRANICE_MIEJSKO_WIEJSKA = ('1602023', 'Branice', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                   'głubczycki', 'powiat')
    OPOLSKIE_GLUBCZYCKI_GLUBCZYCE_MIEJSKO_WIEJSKA = ('1602033', 'Głubczyce', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                     'głubczycki', 'powiat')
    OPOLSKIE_GLUBCZYCKI_KIETRZ_MIEJSKO_WIEJSKA = ('1602043', 'Kietrz', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                  'głubczycki', 'powiat')
    OPOLSKIE_KEDZIERZYNSKO_KOZIELSKI_KEDZIERZYN_KOZLE_MIEJSKA = ('1603011', 'Kędzierzyn-Koźle', GminaType.MIEJSKA,
                                                                 'opolskie', 'kędzierzyńsko-kozielski', 'powiat')
    OPOLSKIE_KEDZIERZYNSKO_KOZIELSKI_BIERAWA_WIEJSKA = ('1603022', 'Bierawa', GminaType.WIEJSKA, 'opolskie',
                                                        'kędzierzyńsko-kozielski', 'powiat')
    OPOLSKIE_KEDZIERZYNSKO_KOZIELSKI_CISEK_WIEJSKA = ('1603032', 'Cisek', GminaType.WIEJSKA, 'opolskie',
                                                      'kędzierzyńsko-kozielski', 'powiat')
    OPOLSKIE_KEDZIERZYNSKO_KOZIELSKI_PAWLOWICZKI_WIEJSKA = ('1603042', 'Pawłowiczki', GminaType.WIEJSKA, 'opolskie',
                                                            'kędzierzyńsko-kozielski', 'powiat')
    OPOLSKIE_KEDZIERZYNSKO_KOZIELSKI_POLSKA_CEREKIEW_WIEJSKA = ('1603052', 'Polska Cerekiew', GminaType.WIEJSKA,
                                                                'opolskie', 'kędzierzyńsko-kozielski', 'powiat')
    OPOLSKIE_KEDZIERZYNSKO_KOZIELSKI_RENSKA_WIES_WIEJSKA = ('1603062', 'Reńska Wieś', GminaType.WIEJSKA, 'opolskie',
                                                            'kędzierzyńsko-kozielski', 'powiat')
    OPOLSKIE_KLUCZBORSKI_BYCZYNA_MIEJSKO_WIEJSKA = ('1604013', 'Byczyna', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                    'kluczborski', 'powiat')
    OPOLSKIE_KLUCZBORSKI_KLUCZBORK_MIEJSKO_WIEJSKA = ('1604023', 'Kluczbork', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                      'kluczborski', 'powiat')
    OPOLSKIE_KLUCZBORSKI_LASOWICE_WIELKIE_WIEJSKA = ('1604032', 'Lasowice Wielkie', GminaType.WIEJSKA, 'opolskie',
                                                     'kluczborski', 'powiat')
    OPOLSKIE_KLUCZBORSKI_WOLCZYN_MIEJSKO_WIEJSKA = ('1604043', 'Wołczyn', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                    'kluczborski', 'powiat')
    OPOLSKIE_KRAPKOWICKI_GOGOLIN_MIEJSKO_WIEJSKA = ('1605013', 'Gogolin', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                    'krapkowicki', 'powiat')
    OPOLSKIE_KRAPKOWICKI_KRAPKOWICE_MIEJSKO_WIEJSKA = ('1605023', 'Krapkowice', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                       'krapkowicki', 'powiat')
    OPOLSKIE_KRAPKOWICKI_STRZELECZKI_MIEJSKO_WIEJSKA = ('1605033', 'Strzeleczki', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                        'krapkowicki', 'powiat')
    OPOLSKIE_KRAPKOWICKI_WALCE_WIEJSKA = ('1605042', 'Walce', GminaType.WIEJSKA, 'opolskie', 'krapkowicki', 'powiat')
    OPOLSKIE_KRAPKOWICKI_ZDZIESZOWICE_MIEJSKO_WIEJSKA = ('1605053', 'Zdzieszowice', GminaType.MIEJSKO_WIEJSKA,
                                                         'opolskie', 'krapkowicki', 'powiat')
    OPOLSKIE_NAMYSLOWSKI_DOMASZOWICE_WIEJSKA = ('1606012', 'Domaszowice', GminaType.WIEJSKA, 'opolskie', 'namysłowski',
                                                'powiat')
    OPOLSKIE_NAMYSLOWSKI_NAMYSLOW_MIEJSKO_WIEJSKA = ('1606023', 'Namysłów', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                     'namysłowski', 'powiat')
    OPOLSKIE_NAMYSLOWSKI_POKOJ_WIEJSKA = ('1606032', 'Pokój', GminaType.WIEJSKA, 'opolskie', 'namysłowski', 'powiat')
    OPOLSKIE_NAMYSLOWSKI_SWIERCZOW_WIEJSKA = ('1606042', 'Świerczów', GminaType.WIEJSKA, 'opolskie', 'namysłowski',
                                              'powiat')
    OPOLSKIE_NAMYSLOWSKI_WILKOW_WIEJSKA = ('1606052', 'Wilków', GminaType.WIEJSKA, 'opolskie', 'namysłowski', 'powiat')
    OPOLSKIE_NYSKI_GLUCHOLAZY_MIEJSKO_WIEJSKA = ('1607013', 'Głuchołazy', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                 'nyski', 'powiat')
    OPOLSKIE_NYSKI_KAMIENNIK_WIEJSKA = ('1607022', 'Kamiennik', GminaType.WIEJSKA, 'opolskie', 'nyski', 'powiat')
    OPOLSKIE_NYSKI_KORFANTOW_MIEJSKO_WIEJSKA = ('1607033', 'Korfantów', GminaType.MIEJSKO_WIEJSKA, 'opolskie', 'nyski',
                                                'powiat')
    OPOLSKIE_NYSKI_LAMBINOWICE_WIEJSKA = ('1607042', 'Łambinowice', GminaType.WIEJSKA, 'opolskie', 'nyski', 'powiat')
    OPOLSKIE_NYSKI_NYSA_MIEJSKO_WIEJSKA = ('1607053', 'Nysa', GminaType.MIEJSKO_WIEJSKA, 'opolskie', 'nyski', 'powiat')
    OPOLSKIE_NYSKI_OTMUCHOW_MIEJSKO_WIEJSKA = ('1607063', 'Otmuchów', GminaType.MIEJSKO_WIEJSKA, 'opolskie', 'nyski',
                                               'powiat')
    OPOLSKIE_NYSKI_PACZKOW_MIEJSKO_WIEJSKA = ('1607073', 'Paczków', GminaType.MIEJSKO_WIEJSKA, 'opolskie', 'nyski',
                                              'powiat')
    OPOLSKIE_NYSKI_PAKOSLAWICE_WIEJSKA = ('1607082', 'Pakosławice', GminaType.WIEJSKA, 'opolskie', 'nyski', 'powiat')
    OPOLSKIE_NYSKI_SKOROSZYCE_WIEJSKA = ('1607092', 'Skoroszyce', GminaType.WIEJSKA, 'opolskie', 'nyski', 'powiat')
    OPOLSKIE_OLESKI_DOBRODZIEN_MIEJSKO_WIEJSKA = ('1608013', 'Dobrodzień', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                  'oleski', 'powiat')
    OPOLSKIE_OLESKI_GORZOW_SLASKI_MIEJSKO_WIEJSKA = ('1608023', 'Gorzów Śląski', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                     'oleski', 'powiat')
    OPOLSKIE_OLESKI_OLESNO_MIEJSKO_WIEJSKA = ('1608033', 'Olesno', GminaType.MIEJSKO_WIEJSKA, 'opolskie', 'oleski',
                                              'powiat')
    OPOLSKIE_OLESKI_PRASZKA_MIEJSKO_WIEJSKA = ('1608043', 'Praszka', GminaType.MIEJSKO_WIEJSKA, 'opolskie', 'oleski',
                                               'powiat')
    OPOLSKIE_OLESKI_RADLOW_WIEJSKA = ('1608052', 'Radłów', GminaType.WIEJSKA, 'opolskie', 'oleski', 'powiat')
    OPOLSKIE_OLESKI_RUDNIKI_WIEJSKA = ('1608062', 'Rudniki', GminaType.WIEJSKA, 'opolskie', 'oleski', 'powiat')
    OPOLSKIE_OLESKI_ZEBOWICE_WIEJSKA = ('1608072', 'Zębowice', GminaType.WIEJSKA, 'opolskie', 'oleski', 'powiat')
    OPOLSKIE_OPOLSKI_CHRZASTOWICE_WIEJSKA = ('1609012', 'Chrząstowice', GminaType.WIEJSKA, 'opolskie', 'opolski',
                                             'powiat')
    OPOLSKIE_OPOLSKI_DABROWA_WIEJSKA = ('1609022', 'Dąbrowa', GminaType.WIEJSKA, 'opolskie', 'opolski', 'powiat')
    OPOLSKIE_OPOLSKI_DOBRZEN_WIELKI_WIEJSKA = ('1609032', 'Dobrzeń Wielki', GminaType.WIEJSKA, 'opolskie', 'opolski',
                                               'powiat')
    OPOLSKIE_OPOLSKI_KOMPRACHCICE_WIEJSKA = ('1609042', 'Komprachcice', GminaType.WIEJSKA, 'opolskie', 'opolski',
                                             'powiat')
    OPOLSKIE_OPOLSKI_LUBNIANY_WIEJSKA = ('1609052', 'Łubniany', GminaType.WIEJSKA, 'opolskie', 'opolski', 'powiat')
    OPOLSKIE_OPOLSKI_MUROW_WIEJSKA = ('1609062', 'Murów', GminaType.WIEJSKA, 'opolskie', 'opolski', 'powiat')
    OPOLSKIE_OPOLSKI_NIEMODLIN_MIEJSKO_WIEJSKA = ('1609073', 'Niemodlin', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                  'opolski', 'powiat')
    OPOLSKIE_OPOLSKI_OZIMEK_MIEJSKO_WIEJSKA = ('1609083', 'Ozimek', GminaType.MIEJSKO_WIEJSKA, 'opolskie', 'opolski',
                                               'powiat')
    OPOLSKIE_OPOLSKI_POPIELOW_WIEJSKA = ('1609092', 'Popielów', GminaType.WIEJSKA, 'opolskie', 'opolski', 'powiat')
    OPOLSKIE_OPOLSKI_PROSZKOW_MIEJSKO_WIEJSKA = ('1609103', 'Prószków', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                 'opolski', 'powiat')
    OPOLSKIE_OPOLSKI_TARNOW_OPOLSKI_WIEJSKA = ('1609112', 'Tarnów Opolski', GminaType.WIEJSKA, 'opolskie', 'opolski',
                                               'powiat')
    OPOLSKIE_OPOLSKI_TULOWICE_MIEJSKO_WIEJSKA = ('1609123', 'Tułowice', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                 'opolski', 'powiat')
    OPOLSKIE_OPOLSKI_TURAWA_WIEJSKA = ('1609132', 'Turawa', GminaType.WIEJSKA, 'opolskie', 'opolski', 'powiat')
    OPOLSKIE_PRUDNICKI_BIALA_MIEJSKO_WIEJSKA = ('1610013', 'Biała', GminaType.MIEJSKO_WIEJSKA, 'opolskie', 'prudnicki',
                                                'powiat')
    OPOLSKIE_PRUDNICKI_GLOGOWEK_MIEJSKO_WIEJSKA = ('1610023', 'Głogówek', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                   'prudnicki', 'powiat')
    OPOLSKIE_PRUDNICKI_LUBRZA_WIEJSKA = ('1610032', 'Lubrza', GminaType.WIEJSKA, 'opolskie', 'prudnicki', 'powiat')
    OPOLSKIE_PRUDNICKI_PRUDNIK_MIEJSKO_WIEJSKA = ('1610043', 'Prudnik', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                  'prudnicki', 'powiat')
    OPOLSKIE_STRZELECKI_IZBICKO_WIEJSKA = ('1611012', 'Izbicko', GminaType.WIEJSKA, 'opolskie', 'strzelecki', 'powiat')
    OPOLSKIE_STRZELECKI_JEMIELNICA_WIEJSKA = ('1611022', 'Jemielnica', GminaType.WIEJSKA, 'opolskie', 'strzelecki',
                                              'powiat')
    OPOLSKIE_STRZELECKI_KOLONOWSKIE_MIEJSKO_WIEJSKA = ('1611033', 'Kolonowskie', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                       'strzelecki', 'powiat')
    OPOLSKIE_STRZELECKI_LESNICA_MIEJSKO_WIEJSKA = ('1611043', 'Leśnica', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                   'strzelecki', 'powiat')
    OPOLSKIE_STRZELECKI_STRZELCE_OPOLSKIE_MIEJSKO_WIEJSKA = ('1611053', 'Strzelce Opolskie', GminaType.MIEJSKO_WIEJSKA,
                                                             'opolskie', 'strzelecki', 'powiat')
    OPOLSKIE_STRZELECKI_UJAZD_MIEJSKO_WIEJSKA = ('1611063', 'Ujazd', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                 'strzelecki', 'powiat')
    OPOLSKIE_STRZELECKI_ZAWADZKIE_MIEJSKO_WIEJSKA = ('1611073', 'Zawadzkie', GminaType.MIEJSKO_WIEJSKA, 'opolskie',
                                                     'strzelecki', 'powiat')
    OPOLSKIE_OPOLE_OPOLE_MIEJSKA = ('1661011', 'Opole', GminaType.MIEJSKA, 'opolskie', 'Opole',
                                    'miasto na prawach powiatu')

    # Podkarpackie
    PODKARPACKIE_BIESZCZADZKI_CZARNA_WIEJSKA = ('1801032', 'Czarna', GminaType.WIEJSKA, 'podkarpackie', 'bieszczadzki',
                                                'powiat')
    PODKARPACKIE_BIESZCZADZKI_LUTOWISKA_WIEJSKA = ('1801052', 'Lutowiska', GminaType.WIEJSKA, 'podkarpackie',
                                                   'bieszczadzki', 'powiat')
    PODKARPACKIE_BIESZCZADZKI_USTRZYKI_DOLNE_MIEJSKO_WIEJSKA = ('1801083', 'Ustrzyki Dolne', GminaType.MIEJSKO_WIEJSKA,
                                                                'podkarpackie', 'bieszczadzki', 'powiat')
    PODKARPACKIE_BRZOZOWSKI_BRZOZOW_MIEJSKO_WIEJSKA = ('1802013', 'Brzozów', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                       'brzozowski', 'powiat')
    PODKARPACKIE_BRZOZOWSKI_DOMARADZ_WIEJSKA = ('1802022', 'Domaradz', GminaType.WIEJSKA, 'podkarpackie', 'brzozowski',
                                                'powiat')
    PODKARPACKIE_BRZOZOWSKI_DYDNIA_WIEJSKA = ('1802032', 'Dydnia', GminaType.WIEJSKA, 'podkarpackie', 'brzozowski',
                                              'powiat')
    PODKARPACKIE_BRZOZOWSKI_HACZOW_WIEJSKA = ('1802042', 'Haczów', GminaType.WIEJSKA, 'podkarpackie', 'brzozowski',
                                              'powiat')
    PODKARPACKIE_BRZOZOWSKI_JASIENICA_ROSIELNA_WIEJSKA = ('1802052', 'Jasienica Rosielna', GminaType.WIEJSKA,
                                                          'podkarpackie', 'brzozowski', 'powiat')
    PODKARPACKIE_BRZOZOWSKI_NOZDRZEC_WIEJSKA = ('1802062', 'Nozdrzec', GminaType.WIEJSKA, 'podkarpackie', 'brzozowski',
                                                'powiat')
    PODKARPACKIE_DEBICKI_DEBICA_MIEJSKA = ('1803011', 'Dębica', GminaType.MIEJSKA, 'podkarpackie', 'dębicki', 'powiat')
    PODKARPACKIE_DEBICKI_BRZOSTEK_MIEJSKO_WIEJSKA = ('1803023', 'Brzostek', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                     'dębicki', 'powiat')
    PODKARPACKIE_DEBICKI_CZARNA_WIEJSKA = ('1803032', 'Czarna', GminaType.WIEJSKA, 'podkarpackie', 'dębicki', 'powiat')
    PODKARPACKIE_DEBICKI_DEBICA_WIEJSKA = ('1803042', 'Dębica', GminaType.WIEJSKA, 'podkarpackie', 'dębicki', 'powiat')
    PODKARPACKIE_DEBICKI_JODLOWA_WIEJSKA = ('1803052', 'Jodłowa', GminaType.WIEJSKA, 'podkarpackie', 'dębicki',
                                            'powiat')
    PODKARPACKIE_DEBICKI_PILZNO_MIEJSKO_WIEJSKA = ('1803063', 'Pilzno', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                   'dębicki', 'powiat')
    PODKARPACKIE_DEBICKI_ZYRAKOW_WIEJSKA = ('1803072', 'Żyraków', GminaType.WIEJSKA, 'podkarpackie', 'dębicki',
                                            'powiat')
    PODKARPACKIE_JAROSLAWSKI_JAROSLAW_MIEJSKA = ('1804011', 'Jarosław', GminaType.MIEJSKA, 'podkarpackie',
                                                 'jarosławski', 'powiat')
    PODKARPACKIE_JAROSLAWSKI_RADYMNO_MIEJSKA = ('1804021', 'Radymno', GminaType.MIEJSKA, 'podkarpackie', 'jarosławski',
                                                'powiat')
    PODKARPACKIE_JAROSLAWSKI_CHLOPICE_WIEJSKA = ('1804032', 'Chłopice', GminaType.WIEJSKA, 'podkarpackie',
                                                 'jarosławski', 'powiat')
    PODKARPACKIE_JAROSLAWSKI_JAROSLAW_WIEJSKA = ('1804042', 'Jarosław', GminaType.WIEJSKA, 'podkarpackie',
                                                 'jarosławski', 'powiat')
    PODKARPACKIE_JAROSLAWSKI_LASZKI_WIEJSKA = ('1804052', 'Laszki', GminaType.WIEJSKA, 'podkarpackie', 'jarosławski',
                                               'powiat')
    PODKARPACKIE_JAROSLAWSKI_PAWLOSIOW_WIEJSKA = ('1804062', 'Pawłosiów', GminaType.WIEJSKA, 'podkarpackie',
                                                  'jarosławski', 'powiat')
    PODKARPACKIE_JAROSLAWSKI_PRUCHNIK_MIEJSKO_WIEJSKA = ('1804073', 'Pruchnik', GminaType.MIEJSKO_WIEJSKA,
                                                         'podkarpackie', 'jarosławski', 'powiat')
    PODKARPACKIE_JAROSLAWSKI_RADYMNO_WIEJSKA = ('1804082', 'Radymno', GminaType.WIEJSKA, 'podkarpackie', 'jarosławski',
                                                'powiat')
    PODKARPACKIE_JAROSLAWSKI_ROKIETNICA_WIEJSKA = ('1804092', 'Rokietnica', GminaType.WIEJSKA, 'podkarpackie',
                                                   'jarosławski', 'powiat')
    PODKARPACKIE_JAROSLAWSKI_ROZWIENICA_WIEJSKA = ('1804102', 'Roźwienica', GminaType.WIEJSKA, 'podkarpackie',
                                                   'jarosławski', 'powiat')
    PODKARPACKIE_JAROSLAWSKI_WIAZOWNICA_WIEJSKA = ('1804112', 'Wiązownica', GminaType.WIEJSKA, 'podkarpackie',
                                                   'jarosławski', 'powiat')
    PODKARPACKIE_JASIELSKI_JASLO_MIEJSKA = ('1805011', 'Jasło', GminaType.MIEJSKA, 'podkarpackie', 'jasielski',
                                            'powiat')
    PODKARPACKIE_JASIELSKI_BRZYSKA_WIEJSKA = ('1805022', 'Brzyska', GminaType.WIEJSKA, 'podkarpackie', 'jasielski',
                                              'powiat')
    PODKARPACKIE_JASIELSKI_DEBOWIEC_WIEJSKA = ('1805032', 'Dębowiec', GminaType.WIEJSKA, 'podkarpackie', 'jasielski',
                                               'powiat')
    PODKARPACKIE_JASIELSKI_JASLO_WIEJSKA = ('1805042', 'Jasło', GminaType.WIEJSKA, 'podkarpackie', 'jasielski',
                                            'powiat')
    PODKARPACKIE_JASIELSKI_KOLACZYCE_MIEJSKO_WIEJSKA = ('1805053', 'Kołaczyce', GminaType.MIEJSKO_WIEJSKA,
                                                        'podkarpackie', 'jasielski', 'powiat')
    PODKARPACKIE_JASIELSKI_KREMPNA_WIEJSKA = ('1805062', 'Krempna', GminaType.WIEJSKA, 'podkarpackie', 'jasielski',
                                              'powiat')
    PODKARPACKIE_JASIELSKI_NOWY_ZMIGROD_WIEJSKA = ('1805072', 'Nowy Żmigród', GminaType.WIEJSKA, 'podkarpackie',
                                                   'jasielski', 'powiat')
    PODKARPACKIE_JASIELSKI_OSIEK_JASIELSKI_WIEJSKA = ('1805082', 'Osiek Jasielski', GminaType.WIEJSKA, 'podkarpackie',
                                                      'jasielski', 'powiat')
    PODKARPACKIE_JASIELSKI_SKOLYSZYN_WIEJSKA = ('1805092', 'Skołyszyn', GminaType.WIEJSKA, 'podkarpackie', 'jasielski',
                                                'powiat')
    PODKARPACKIE_JASIELSKI_TARNOWIEC_WIEJSKA = ('1805112', 'Tarnowiec', GminaType.WIEJSKA, 'podkarpackie', 'jasielski',
                                                'powiat')
    PODKARPACKIE_KOLBUSZOWSKI_CMOLAS_WIEJSKA = ('1806012', 'Cmolas', GminaType.WIEJSKA, 'podkarpackie', 'kolbuszowski',
                                                'powiat')
    PODKARPACKIE_KOLBUSZOWSKI_KOLBUSZOWA_MIEJSKO_WIEJSKA = ('1806023', 'Kolbuszowa', GminaType.MIEJSKO_WIEJSKA,
                                                            'podkarpackie', 'kolbuszowski', 'powiat')
    PODKARPACKIE_KOLBUSZOWSKI_MAJDAN_KROLEWSKI_WIEJSKA = ('1806032', 'Majdan Królewski', GminaType.WIEJSKA,
                                                          'podkarpackie', 'kolbuszowski', 'powiat')
    PODKARPACKIE_KOLBUSZOWSKI_NIWISKA_WIEJSKA = ('1806042', 'Niwiska', GminaType.WIEJSKA, 'podkarpackie',
                                                 'kolbuszowski', 'powiat')
    PODKARPACKIE_KOLBUSZOWSKI_RANIZOW_WIEJSKA = ('1806052', 'Raniżów', GminaType.WIEJSKA, 'podkarpackie',
                                                 'kolbuszowski', 'powiat')
    PODKARPACKIE_KOLBUSZOWSKI_DZIKOWIEC_WIEJSKA = ('1806062', 'Dzikowiec', GminaType.WIEJSKA, 'podkarpackie',
                                                   'kolbuszowski', 'powiat')
    PODKARPACKIE_KROSNIENSKI_CHORKOWKA_WIEJSKA = ('1807012', 'Chorkówka', GminaType.WIEJSKA, 'podkarpackie',
                                                  'krośnieński', 'powiat')
    PODKARPACKIE_KROSNIENSKI_DUKLA_MIEJSKO_WIEJSKA = ('1807023', 'Dukla', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                      'krośnieński', 'powiat')
    PODKARPACKIE_KROSNIENSKI_IWONICZ_ZDROJ_MIEJSKO_WIEJSKA = ('1807033', 'Iwonicz-Zdrój', GminaType.MIEJSKO_WIEJSKA,
                                                              'podkarpackie', 'krośnieński', 'powiat')
    PODKARPACKIE_KROSNIENSKI_JEDLICZE_MIEJSKO_WIEJSKA = ('1807043', 'Jedlicze', GminaType.MIEJSKO_WIEJSKA,
                                                         'podkarpackie', 'krośnieński', 'powiat')
    PODKARPACKIE_KROSNIENSKI_KORCZYNA_WIEJSKA = ('1807052', 'Korczyna', GminaType.WIEJSKA, 'podkarpackie',
                                                 'krośnieński', 'powiat')
    PODKARPACKIE_KROSNIENSKI_KROSCIENKO_WYZNE_WIEJSKA = ('1807062', 'Krościenko Wyżne', GminaType.WIEJSKA,
                                                         'podkarpackie', 'krośnieński', 'powiat')
    PODKARPACKIE_KROSNIENSKI_MIEJSCE_PIASTOWE_WIEJSKA = ('1807072', 'Miejsce Piastowe', GminaType.WIEJSKA,
                                                         'podkarpackie', 'krośnieński', 'powiat')
    PODKARPACKIE_KROSNIENSKI_RYMANOW_MIEJSKO_WIEJSKA = ('1807083', 'Rymanów', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                        'krośnieński', 'powiat')
    PODKARPACKIE_KROSNIENSKI_WOJASZOWKA_WIEJSKA = ('1807092', 'Wojaszówka', GminaType.WIEJSKA, 'podkarpackie',
                                                   'krośnieński', 'powiat')
    PODKARPACKIE_KROSNIENSKI_JASLISKA_WIEJSKA = ('1807102', 'Jaśliska', GminaType.WIEJSKA, 'podkarpackie',
                                                 'krośnieński', 'powiat')
    PODKARPACKIE_LEZAJSKI_LEZAJSK_MIEJSKA = ('1808011', 'Leżajsk', GminaType.MIEJSKA, 'podkarpackie', 'leżajski',
                                             'powiat')
    PODKARPACKIE_LEZAJSKI_GRODZISKO_DOLNE_WIEJSKA = ('1808022', 'Grodzisko Dolne', GminaType.WIEJSKA, 'podkarpackie',
                                                     'leżajski', 'powiat')
    PODKARPACKIE_LEZAJSKI_KURYLOWKA_WIEJSKA = ('1808032', 'Kuryłówka', GminaType.WIEJSKA, 'podkarpackie', 'leżajski',
                                               'powiat')
    PODKARPACKIE_LEZAJSKI_LEZAJSK_WIEJSKA = ('1808042', 'Leżajsk', GminaType.WIEJSKA, 'podkarpackie', 'leżajski',
                                             'powiat')
    PODKARPACKIE_LEZAJSKI_NOWA_SARZYNA_MIEJSKO_WIEJSKA = ('1808053', 'Nowa Sarzyna', GminaType.MIEJSKO_WIEJSKA,
                                                          'podkarpackie', 'leżajski', 'powiat')
    PODKARPACKIE_LUBACZOWSKI_LUBACZOW_MIEJSKA = ('1809011', 'Lubaczów', GminaType.MIEJSKA, 'podkarpackie',
                                                 'lubaczowski', 'powiat')
    PODKARPACKIE_LUBACZOWSKI_CIESZANOW_MIEJSKO_WIEJSKA = ('1809023', 'Cieszanów', GminaType.MIEJSKO_WIEJSKA,
                                                          'podkarpackie', 'lubaczowski', 'powiat')
    PODKARPACKIE_LUBACZOWSKI_HORYNIEC_ZDROJ_WIEJSKA = ('1809032', 'Horyniec-Zdrój', GminaType.WIEJSKA, 'podkarpackie',
                                                       'lubaczowski', 'powiat')
    PODKARPACKIE_LUBACZOWSKI_LUBACZOW_WIEJSKA = ('1809042', 'Lubaczów', GminaType.WIEJSKA, 'podkarpackie',
                                                 'lubaczowski', 'powiat')
    PODKARPACKIE_LUBACZOWSKI_NAROL_MIEJSKO_WIEJSKA = ('1809053', 'Narol', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                      'lubaczowski', 'powiat')
    PODKARPACKIE_LUBACZOWSKI_OLESZYCE_MIEJSKO_WIEJSKA = ('1809063', 'Oleszyce', GminaType.MIEJSKO_WIEJSKA,
                                                         'podkarpackie', 'lubaczowski', 'powiat')
    PODKARPACKIE_LUBACZOWSKI_STARY_DZIKOW_WIEJSKA = ('1809072', 'Stary Dzików', GminaType.WIEJSKA, 'podkarpackie',
                                                     'lubaczowski', 'powiat')
    PODKARPACKIE_LUBACZOWSKI_WIELKIE_OCZY_WIEJSKA = ('1809082', 'Wielkie Oczy', GminaType.WIEJSKA, 'podkarpackie',
                                                     'lubaczowski', 'powiat')
    PODKARPACKIE_LANCUCKI_LANCUT_MIEJSKA = ('1810011', 'Łańcut', GminaType.MIEJSKA, 'podkarpackie', 'łańcucki',
                                            'powiat')
    PODKARPACKIE_LANCUCKI_BIALOBRZEGI_WIEJSKA = ('1810022', 'Białobrzegi', GminaType.WIEJSKA, 'podkarpackie',
                                                 'łańcucki', 'powiat')
    PODKARPACKIE_LANCUCKI_CZARNA_WIEJSKA = ('1810032', 'Czarna', GminaType.WIEJSKA, 'podkarpackie', 'łańcucki',
                                            'powiat')
    PODKARPACKIE_LANCUCKI_LANCUT_WIEJSKA = ('1810042', 'Łańcut', GminaType.WIEJSKA, 'podkarpackie', 'łańcucki',
                                            'powiat')
    PODKARPACKIE_LANCUCKI_MARKOWA_WIEJSKA = ('1810052', 'Markowa', GminaType.WIEJSKA, 'podkarpackie', 'łańcucki',
                                             'powiat')
    PODKARPACKIE_LANCUCKI_RAKSZAWA_WIEJSKA = ('1810062', 'Rakszawa', GminaType.WIEJSKA, 'podkarpackie', 'łańcucki',
                                              'powiat')
    PODKARPACKIE_LANCUCKI_ZOLYNIA_WIEJSKA = ('1810072', 'Żołynia', GminaType.WIEJSKA, 'podkarpackie', 'łańcucki',
                                             'powiat')
    PODKARPACKIE_MIELECKI_MIELEC_MIEJSKA = ('1811011', 'Mielec', GminaType.MIEJSKA, 'podkarpackie', 'mielecki',
                                            'powiat')
    PODKARPACKIE_MIELECKI_BOROWA_WIEJSKA = ('1811022', 'Borowa', GminaType.WIEJSKA, 'podkarpackie', 'mielecki',
                                            'powiat')
    PODKARPACKIE_MIELECKI_CZERMIN_WIEJSKA = ('1811032', 'Czermin', GminaType.WIEJSKA, 'podkarpackie', 'mielecki',
                                             'powiat')
    PODKARPACKIE_MIELECKI_GAWLUSZOWICE_WIEJSKA = ('1811042', 'Gawłuszowice', GminaType.WIEJSKA, 'podkarpackie',
                                                  'mielecki', 'powiat')
    PODKARPACKIE_MIELECKI_MIELEC_WIEJSKA = ('1811052', 'Mielec', GminaType.WIEJSKA, 'podkarpackie', 'mielecki',
                                            'powiat')
    PODKARPACKIE_MIELECKI_PADEW_NARODOWA_WIEJSKA = ('1811062', 'Padew Narodowa', GminaType.WIEJSKA, 'podkarpackie',
                                                    'mielecki', 'powiat')
    PODKARPACKIE_MIELECKI_PRZECLAW_MIEJSKO_WIEJSKA = ('1811073', 'Przecław', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                      'mielecki', 'powiat')
    PODKARPACKIE_MIELECKI_RADOMYSL_WIELKI_MIEJSKO_WIEJSKA = ('1811083', 'Radomyśl Wielki', GminaType.MIEJSKO_WIEJSKA,
                                                             'podkarpackie', 'mielecki', 'powiat')
    PODKARPACKIE_MIELECKI_TUSZOW_NARODOWY_WIEJSKA = ('1811092', 'Tuszów Narodowy', GminaType.WIEJSKA, 'podkarpackie',
                                                     'mielecki', 'powiat')
    PODKARPACKIE_MIELECKI_WADOWICE_GORNE_WIEJSKA = ('1811102', 'Wadowice Górne', GminaType.WIEJSKA, 'podkarpackie',
                                                    'mielecki', 'powiat')
    PODKARPACKIE_NIZANSKI_HARASIUKI_WIEJSKA = ('1812012', 'Harasiuki', GminaType.WIEJSKA, 'podkarpackie', 'niżański',
                                               'powiat')
    PODKARPACKIE_NIZANSKI_JAROCIN_WIEJSKA = ('1812022', 'Jarocin', GminaType.WIEJSKA, 'podkarpackie', 'niżański',
                                             'powiat')
    PODKARPACKIE_NIZANSKI_JEZOWE_WIEJSKA = ('1812032', 'Jeżowe', GminaType.WIEJSKA, 'podkarpackie', 'niżański',
                                            'powiat')
    PODKARPACKIE_NIZANSKI_KRZESZOW_WIEJSKA = ('1812042', 'Krzeszów', GminaType.WIEJSKA, 'podkarpackie', 'niżański',
                                              'powiat')
    PODKARPACKIE_NIZANSKI_NISKO_MIEJSKO_WIEJSKA = ('1812053', 'Nisko', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                   'niżański', 'powiat')
    PODKARPACKIE_NIZANSKI_RUDNIK_NAD_SANEM_MIEJSKO_WIEJSKA = ('1812063', 'Rudnik nad Sanem', GminaType.MIEJSKO_WIEJSKA,
                                                              'podkarpackie', 'niżański', 'powiat')
    PODKARPACKIE_NIZANSKI_ULANOW_MIEJSKO_WIEJSKA = ('1812073', 'Ulanów', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                    'niżański', 'powiat')
    PODKARPACKIE_PRZEMYSKI_BIRCZA_MIEJSKO_WIEJSKA = ('1813013', 'Bircza', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                     'przemyski', 'powiat')
    PODKARPACKIE_PRZEMYSKI_DUBIECKO_MIEJSKO_WIEJSKA = ('1813023', 'Dubiecko', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                       'przemyski', 'powiat')
    PODKARPACKIE_PRZEMYSKI_FREDROPOL_WIEJSKA = ('1813032', 'Fredropol', GminaType.WIEJSKA, 'podkarpackie', 'przemyski',
                                                'powiat')
    PODKARPACKIE_PRZEMYSKI_KRASICZYN_WIEJSKA = ('1813042', 'Krasiczyn', GminaType.WIEJSKA, 'podkarpackie', 'przemyski',
                                                'powiat')
    PODKARPACKIE_PRZEMYSKI_KRZYWCZA_WIEJSKA = ('1813052', 'Krzywcza', GminaType.WIEJSKA, 'podkarpackie', 'przemyski',
                                               'powiat')
    PODKARPACKIE_PRZEMYSKI_MEDYKA_WIEJSKA = ('1813062', 'Medyka', GminaType.WIEJSKA, 'podkarpackie', 'przemyski',
                                             'powiat')
    PODKARPACKIE_PRZEMYSKI_ORLY_WIEJSKA = ('1813072', 'Orły', GminaType.WIEJSKA, 'podkarpackie', 'przemyski', 'powiat')
    PODKARPACKIE_PRZEMYSKI_PRZEMYSL_WIEJSKA = ('1813082', 'Przemyśl', GminaType.WIEJSKA, 'podkarpackie', 'przemyski',
                                               'powiat')
    PODKARPACKIE_PRZEMYSKI_STUBNO_WIEJSKA = ('1813092', 'Stubno', GminaType.WIEJSKA, 'podkarpackie', 'przemyski',
                                             'powiat')
    PODKARPACKIE_PRZEMYSKI_ZURAWICA_WIEJSKA = ('1813102', 'Żurawica', GminaType.WIEJSKA, 'podkarpackie', 'przemyski',
                                               'powiat')
    PODKARPACKIE_PRZEWORSKI_PRZEWORSK_MIEJSKA = ('1814011', 'Przeworsk', GminaType.MIEJSKA, 'podkarpackie',
                                                 'przeworski', 'powiat')
    PODKARPACKIE_PRZEWORSKI_ADAMOWKA_WIEJSKA = ('1814022', 'Adamówka', GminaType.WIEJSKA, 'podkarpackie', 'przeworski',
                                                'powiat')
    PODKARPACKIE_PRZEWORSKI_GAC_WIEJSKA = ('1814032', 'Gać', GminaType.WIEJSKA, 'podkarpackie', 'przeworski', 'powiat')
    PODKARPACKIE_PRZEWORSKI_JAWORNIK_POLSKI_MIEJSKO_WIEJSKA = ('1814043', 'Jawornik Polski', GminaType.MIEJSKO_WIEJSKA,
                                                               'podkarpackie', 'przeworski', 'powiat')
    PODKARPACKIE_PRZEWORSKI_KANCZUGA_MIEJSKO_WIEJSKA = ('1814053', 'Kańczuga', GminaType.MIEJSKO_WIEJSKA,
                                                        'podkarpackie', 'przeworski', 'powiat')
    PODKARPACKIE_PRZEWORSKI_PRZEWORSK_WIEJSKA = ('1814062', 'Przeworsk', GminaType.WIEJSKA, 'podkarpackie',
                                                 'przeworski', 'powiat')
    PODKARPACKIE_PRZEWORSKI_SIENIAWA_MIEJSKO_WIEJSKA = ('1814073', 'Sieniawa', GminaType.MIEJSKO_WIEJSKA,
                                                        'podkarpackie', 'przeworski', 'powiat')
    PODKARPACKIE_PRZEWORSKI_TRYNCZA_WIEJSKA = ('1814082', 'Tryńcza', GminaType.WIEJSKA, 'podkarpackie', 'przeworski',
                                               'powiat')
    PODKARPACKIE_PRZEWORSKI_ZARZECZE_WIEJSKA = ('1814092', 'Zarzecze', GminaType.WIEJSKA, 'podkarpackie', 'przeworski',
                                                'powiat')
    PODKARPACKIE_ROPCZYCKO_SEDZISZOWSKI_IWIERZYCE_WIEJSKA = ('1815012', 'Iwierzyce', GminaType.WIEJSKA, 'podkarpackie',
                                                             'ropczycko-sędziszowski', 'powiat')
    PODKARPACKIE_ROPCZYCKO_SEDZISZOWSKI_OSTROW_WIEJSKA = ('1815022', 'Ostrów', GminaType.WIEJSKA, 'podkarpackie',
                                                          'ropczycko-sędziszowski', 'powiat')
    PODKARPACKIE_ROPCZYCKO_SEDZISZOWSKI_ROPCZYCE_MIEJSKO_WIEJSKA = ('1815033', 'Ropczyce', GminaType.MIEJSKO_WIEJSKA,
                                                                    'podkarpackie', 'ropczycko-sędziszowski', 'powiat')
    PODKARPACKIE_ROPCZYCKO_SEDZISZOWSKI_SEDZISZOW_MALOPOLSKI_MIEJSKO_WIEJSKA = ('1815043', 'Sędziszów Małopolski',
                                                                                GminaType.MIEJSKO_WIEJSKA,
                                                                                'podkarpackie',
                                                                                'ropczycko-sędziszowski', 'powiat')
    PODKARPACKIE_ROPCZYCKO_SEDZISZOWSKI_WIELOPOLE_SKRZYNSKIE_WIEJSKA = ('1815052', 'Wielopole Skrzyńskie',
                                                                        GminaType.WIEJSKA, 'podkarpackie',
                                                                        'ropczycko-sędziszowski', 'powiat')
    PODKARPACKIE_RZESZOWSKI_DYNOW_MIEJSKA = ('1816011', 'Dynów', GminaType.MIEJSKA, 'podkarpackie', 'rzeszowski',
                                             'powiat')
    PODKARPACKIE_RZESZOWSKI_BLAZOWA_MIEJSKO_WIEJSKA = ('1816023', 'Błażowa', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                       'rzeszowski', 'powiat')
    PODKARPACKIE_RZESZOWSKI_BOGUCHWALA_MIEJSKO_WIEJSKA = ('1816033', 'Boguchwała', GminaType.MIEJSKO_WIEJSKA,
                                                          'podkarpackie', 'rzeszowski', 'powiat')
    PODKARPACKIE_RZESZOWSKI_CHMIELNIK_WIEJSKA = ('1816042', 'Chmielnik', GminaType.WIEJSKA, 'podkarpackie',
                                                 'rzeszowski', 'powiat')
    PODKARPACKIE_RZESZOWSKI_DYNOW_WIEJSKA = ('1816052', 'Dynów', GminaType.WIEJSKA, 'podkarpackie', 'rzeszowski',
                                             'powiat')
    PODKARPACKIE_RZESZOWSKI_GLOGOW_MALOPOLSKI_MIEJSKO_WIEJSKA = ('1816063', 'Głogów Małopolski',
                                                                 GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                                 'rzeszowski', 'powiat')
    PODKARPACKIE_RZESZOWSKI_HYZNE_WIEJSKA = ('1816072', 'Hyżne', GminaType.WIEJSKA, 'podkarpackie', 'rzeszowski',
                                             'powiat')
    PODKARPACKIE_RZESZOWSKI_KAMIEN_WIEJSKA = ('1816082', 'Kamień', GminaType.WIEJSKA, 'podkarpackie', 'rzeszowski',
                                              'powiat')
    PODKARPACKIE_RZESZOWSKI_KRASNE_WIEJSKA = ('1816092', 'Krasne', GminaType.WIEJSKA, 'podkarpackie', 'rzeszowski',
                                              'powiat')
    PODKARPACKIE_RZESZOWSKI_LUBENIA_WIEJSKA = ('1816102', 'Lubenia', GminaType.WIEJSKA, 'podkarpackie', 'rzeszowski',
                                               'powiat')
    PODKARPACKIE_RZESZOWSKI_SOKOLOW_MALOPOLSKI_MIEJSKO_WIEJSKA = ('1816113', 'Sokołów Małopolski',
                                                                  GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                                  'rzeszowski', 'powiat')
    PODKARPACKIE_RZESZOWSKI_SWILCZA_WIEJSKA = ('1816122', 'Świlcza', GminaType.WIEJSKA, 'podkarpackie', 'rzeszowski',
                                               'powiat')
    PODKARPACKIE_RZESZOWSKI_TRZEBOWNISKO_WIEJSKA = ('1816132', 'Trzebownisko', GminaType.WIEJSKA, 'podkarpackie',
                                                    'rzeszowski', 'powiat')
    PODKARPACKIE_RZESZOWSKI_TYCZYN_MIEJSKO_WIEJSKA = ('1816143', 'Tyczyn', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                      'rzeszowski', 'powiat')
    PODKARPACKIE_SANOCKI_SANOK_MIEJSKA = ('1817011', 'Sanok', GminaType.MIEJSKA, 'podkarpackie', 'sanocki', 'powiat')
    PODKARPACKIE_SANOCKI_BESKO_WIEJSKA = ('1817022', 'Besko', GminaType.WIEJSKA, 'podkarpackie', 'sanocki', 'powiat')
    PODKARPACKIE_SANOCKI_BUKOWSKO_WIEJSKA = ('1817032', 'Bukowsko', GminaType.WIEJSKA, 'podkarpackie', 'sanocki',
                                             'powiat')
    PODKARPACKIE_SANOCKI_KOMANCZA_WIEJSKA = ('1817042', 'Komańcza', GminaType.WIEJSKA, 'podkarpackie', 'sanocki',
                                             'powiat')
    PODKARPACKIE_SANOCKI_SANOK_WIEJSKA = ('1817052', 'Sanok', GminaType.WIEJSKA, 'podkarpackie', 'sanocki', 'powiat')
    PODKARPACKIE_SANOCKI_TYRAWA_WOLOSKA_WIEJSKA = ('1817062', 'Tyrawa Wołoska', GminaType.WIEJSKA, 'podkarpackie',
                                                   'sanocki', 'powiat')
    PODKARPACKIE_SANOCKI_ZAGORZ_MIEJSKO_WIEJSKA = ('1817073', 'Zagórz', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                   'sanocki', 'powiat')
    PODKARPACKIE_SANOCKI_ZARSZYN_WIEJSKA = ('1817082', 'Zarszyn', GminaType.WIEJSKA, 'podkarpackie', 'sanocki',
                                            'powiat')
    PODKARPACKIE_STALOWOWOLSKI_STALOWA_WOLA_MIEJSKA = ('1818011', 'Stalowa Wola', GminaType.MIEJSKA, 'podkarpackie',
                                                       'stalowowolski', 'powiat')
    PODKARPACKIE_STALOWOWOLSKI_BOJANOW_WIEJSKA = ('1818022', 'Bojanów', GminaType.WIEJSKA, 'podkarpackie',
                                                  'stalowowolski', 'powiat')
    PODKARPACKIE_STALOWOWOLSKI_PYSZNICA_WIEJSKA = ('1818032', 'Pysznica', GminaType.WIEJSKA, 'podkarpackie',
                                                   'stalowowolski', 'powiat')
    PODKARPACKIE_STALOWOWOLSKI_RADOMYSL_NAD_SANEM_WIEJSKA = ('1818042', 'Radomyśl nad Sanem', GminaType.WIEJSKA,
                                                             'podkarpackie', 'stalowowolski', 'powiat')
    PODKARPACKIE_STALOWOWOLSKI_ZAKLIKOW_MIEJSKO_WIEJSKA = ('1818053', 'Zaklików', GminaType.MIEJSKO_WIEJSKA,
                                                           'podkarpackie', 'stalowowolski', 'powiat')
    PODKARPACKIE_STALOWOWOLSKI_ZALESZANY_WIEJSKA = ('1818062', 'Zaleszany', GminaType.WIEJSKA, 'podkarpackie',
                                                    'stalowowolski', 'powiat')
    PODKARPACKIE_STRZYZOWSKI_CZUDEC_WIEJSKA = ('1819012', 'Czudec', GminaType.WIEJSKA, 'podkarpackie', 'strzyżowski',
                                               'powiat')
    PODKARPACKIE_STRZYZOWSKI_FRYSZTAK_WIEJSKA = ('1819022', 'Frysztak', GminaType.WIEJSKA, 'podkarpackie',
                                                 'strzyżowski', 'powiat')
    PODKARPACKIE_STRZYZOWSKI_NIEBYLEC_WIEJSKA = ('1819032', 'Niebylec', GminaType.WIEJSKA, 'podkarpackie',
                                                 'strzyżowski', 'powiat')
    PODKARPACKIE_STRZYZOWSKI_STRZYZOW_MIEJSKO_WIEJSKA = ('1819043', 'Strzyżów', GminaType.MIEJSKO_WIEJSKA,
                                                         'podkarpackie', 'strzyżowski', 'powiat')
    PODKARPACKIE_STRZYZOWSKI_WISNIOWA_WIEJSKA = ('1819052', 'Wiśniowa', GminaType.WIEJSKA, 'podkarpackie',
                                                 'strzyżowski', 'powiat')
    PODKARPACKIE_TARNOBRZESKI_BARANOW_SANDOMIERSKI_MIEJSKO_WIEJSKA = ('1820013', 'Baranów Sandomierski',
                                                                      GminaType.MIEJSKO_WIEJSKA, 'podkarpackie',
                                                                      'tarnobrzeski', 'powiat')
    PODKARPACKIE_TARNOBRZESKI_GORZYCE_WIEJSKA = ('1820022', 'Gorzyce', GminaType.WIEJSKA, 'podkarpackie',
                                                 'tarnobrzeski', 'powiat')
    PODKARPACKIE_TARNOBRZESKI_GREBOW_WIEJSKA = ('1820032', 'Grębów', GminaType.WIEJSKA, 'podkarpackie', 'tarnobrzeski',
                                                'powiat')
    PODKARPACKIE_TARNOBRZESKI_NOWA_DEBA_MIEJSKO_WIEJSKA = ('1820043', 'Nowa Dęba', GminaType.MIEJSKO_WIEJSKA,
                                                           'podkarpackie', 'tarnobrzeski', 'powiat')
    PODKARPACKIE_LESKI_BALIGROD_WIEJSKA = ('1821012', 'Baligród', GminaType.WIEJSKA, 'podkarpackie', 'leski', 'powiat')
    PODKARPACKIE_LESKI_CISNA_WIEJSKA = ('1821022', 'Cisna', GminaType.WIEJSKA, 'podkarpackie', 'leski', 'powiat')
    PODKARPACKIE_LESKI_LESKO_MIEJSKO_WIEJSKA = ('1821033', 'Lesko', GminaType.MIEJSKO_WIEJSKA, 'podkarpackie', 'leski',
                                                'powiat')
    PODKARPACKIE_LESKI_OLSZANICA_WIEJSKA = ('1821042', 'Olszanica', GminaType.WIEJSKA, 'podkarpackie', 'leski',
                                            'powiat')
    PODKARPACKIE_LESKI_SOLINA_WIEJSKA = ('1821052', 'Solina', GminaType.WIEJSKA, 'podkarpackie', 'leski', 'powiat')
    PODKARPACKIE_KROSNO_KROSNO_MIEJSKA = ('1861011', 'Krosno', GminaType.MIEJSKA, 'podkarpackie', 'Krosno',
                                          'miasto na prawach powiatu')
    PODKARPACKIE_PRZEMYSL_PRZEMYSL_MIEJSKA = ('1862011', 'Przemyśl', GminaType.MIEJSKA, 'podkarpackie', 'Przemyśl',
                                              'miasto na prawach powiatu')
    PODKARPACKIE_RZESZOW_RZESZOW_MIEJSKA = ('1863011', 'Rzeszów', GminaType.MIEJSKA, 'podkarpackie', 'Rzeszów',
                                            'miasto na prawach powiatu')
    PODKARPACKIE_TARNOBRZEG_TARNOBRZEG_MIEJSKA = ('1864011', 'Tarnobrzeg', GminaType.MIEJSKA, 'podkarpackie',
                                                  'Tarnobrzeg', 'miasto na prawach powiatu')

    # Podlaskie
    PODLASKIE_AUGUSTOWSKI_AUGUSTOW_MIEJSKA = ('2001011', 'Augustów', GminaType.MIEJSKA, 'podlaskie', 'augustowski',
                                              'powiat')
    PODLASKIE_AUGUSTOWSKI_AUGUSTOW_WIEJSKA = ('2001022', 'Augustów', GminaType.WIEJSKA, 'podlaskie', 'augustowski',
                                              'powiat')
    PODLASKIE_AUGUSTOWSKI_BARGLOW_KOSCIELNY_WIEJSKA = ('2001032', 'Bargłów Kościelny', GminaType.WIEJSKA, 'podlaskie',
                                                       'augustowski', 'powiat')
    PODLASKIE_AUGUSTOWSKI_LIPSK_MIEJSKO_WIEJSKA = ('2001043', 'Lipsk', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                   'augustowski', 'powiat')
    PODLASKIE_AUGUSTOWSKI_NOWINKA_WIEJSKA = ('2001052', 'Nowinka', GminaType.WIEJSKA, 'podlaskie', 'augustowski',
                                             'powiat')
    PODLASKIE_AUGUSTOWSKI_PLASKA_WIEJSKA = ('2001062', 'Płaska', GminaType.WIEJSKA, 'podlaskie', 'augustowski',
                                            'powiat')
    PODLASKIE_AUGUSTOWSKI_SZTABIN_WIEJSKA = ('2001072', 'Sztabin', GminaType.WIEJSKA, 'podlaskie', 'augustowski',
                                             'powiat')
    PODLASKIE_BIALOSTOCKI_CHOROSZCZ_MIEJSKO_WIEJSKA = ('2002013', 'Choroszcz', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                       'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_CZARNA_BIALOSTOCKA_MIEJSKO_WIEJSKA = ('2002023', 'Czarna Białostocka',
                                                                GminaType.MIEJSKO_WIEJSKA, 'podlaskie', 'białostocki',
                                                                'powiat')
    PODLASKIE_BIALOSTOCKI_DOBRZYNIEWO_DUZE_WIEJSKA = ('2002032', 'Dobrzyniewo Duże', GminaType.WIEJSKA, 'podlaskie',
                                                      'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_GRODEK_WIEJSKA = ('2002042', 'Gródek', GminaType.WIEJSKA, 'podlaskie', 'białostocki',
                                            'powiat')
    PODLASKIE_BIALOSTOCKI_JUCHNOWIEC_KOSCIELNY_WIEJSKA = ('2002052', 'Juchnowiec Kościelny', GminaType.WIEJSKA,
                                                          'podlaskie', 'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_LAPY_MIEJSKO_WIEJSKA = ('2002063', 'Łapy', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                  'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_MICHALOWO_MIEJSKO_WIEJSKA = ('2002073', 'Michałowo', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                       'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_POSWIETNE_WIEJSKA = ('2002082', 'Poświętne', GminaType.WIEJSKA, 'podlaskie', 'białostocki',
                                               'powiat')
    PODLASKIE_BIALOSTOCKI_SUPRASL_MIEJSKO_WIEJSKA = ('2002093', 'Supraśl', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                     'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_SURAZ_MIEJSKO_WIEJSKA = ('2002103', 'Suraż', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                   'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_TUROSN_KOSCIELNA_WIEJSKA = ('2002112', 'Turośń Kościelna', GminaType.WIEJSKA, 'podlaskie',
                                                      'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_TYKOCIN_MIEJSKO_WIEJSKA = ('2002123', 'Tykocin', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                     'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_WASILKOW_MIEJSKO_WIEJSKA = ('2002133', 'Wasilków', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                      'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_ZABLUDOW_MIEJSKO_WIEJSKA = ('2002143', 'Zabłudów', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                      'białostocki', 'powiat')
    PODLASKIE_BIALOSTOCKI_ZAWADY_WIEJSKA = ('2002152', 'Zawady', GminaType.WIEJSKA, 'podlaskie', 'białostocki',
                                            'powiat')
    PODLASKIE_BIALOSTOCKI_GRABOWKA_WIEJSKA = ('2002162', 'Grabówka', GminaType.WIEJSKA, 'podlaskie', 'białostocki',
                                              'powiat')
    PODLASKIE_BIELSKI_BIELSK_PODLASKI_MIEJSKA = ('2003011', 'Bielsk Podlaski', GminaType.MIEJSKA, 'podlaskie',
                                                 'bielski', 'powiat')
    PODLASKIE_BIELSKI_BRANSK_MIEJSKA = ('2003021', 'Brańsk', GminaType.MIEJSKA, 'podlaskie', 'bielski', 'powiat')
    PODLASKIE_BIELSKI_BIELSK_PODLASKI_WIEJSKA = ('2003032', 'Bielsk Podlaski', GminaType.WIEJSKA, 'podlaskie',
                                                 'bielski', 'powiat')
    PODLASKIE_BIELSKI_BOCKI_WIEJSKA = ('2003042', 'Boćki', GminaType.WIEJSKA, 'podlaskie', 'bielski', 'powiat')
    PODLASKIE_BIELSKI_BRANSK_WIEJSKA = ('2003052', 'Brańsk', GminaType.WIEJSKA, 'podlaskie', 'bielski', 'powiat')
    PODLASKIE_BIELSKI_ORLA_WIEJSKA = ('2003062', 'Orla', GminaType.WIEJSKA, 'podlaskie', 'bielski', 'powiat')
    PODLASKIE_BIELSKI_RUDKA_WIEJSKA = ('2003072', 'Rudka', GminaType.WIEJSKA, 'podlaskie', 'bielski', 'powiat')
    PODLASKIE_BIELSKI_WYSZKI_WIEJSKA = ('2003082', 'Wyszki', GminaType.WIEJSKA, 'podlaskie', 'bielski', 'powiat')
    PODLASKIE_GRAJEWSKI_GRAJEWO_MIEJSKA = ('2004011', 'Grajewo', GminaType.MIEJSKA, 'podlaskie', 'grajewski', 'powiat')
    PODLASKIE_GRAJEWSKI_GRAJEWO_WIEJSKA = ('2004022', 'Grajewo', GminaType.WIEJSKA, 'podlaskie', 'grajewski', 'powiat')
    PODLASKIE_GRAJEWSKI_RADZILOW_WIEJSKA = ('2004032', 'Radziłów', GminaType.WIEJSKA, 'podlaskie', 'grajewski',
                                            'powiat')
    PODLASKIE_GRAJEWSKI_RAJGROD_MIEJSKO_WIEJSKA = ('2004043', 'Rajgród', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                   'grajewski', 'powiat')
    PODLASKIE_GRAJEWSKI_SZCZUCZYN_MIEJSKO_WIEJSKA = ('2004053', 'Szczuczyn', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                     'grajewski', 'powiat')
    PODLASKIE_GRAJEWSKI_WASOSZ_WIEJSKA = ('2004062', 'Wąsosz', GminaType.WIEJSKA, 'podlaskie', 'grajewski', 'powiat')
    PODLASKIE_HAJNOWSKI_HAJNOWKA_MIEJSKA = ('2005011', 'Hajnówka', GminaType.MIEJSKA, 'podlaskie', 'hajnowski',
                                            'powiat')
    PODLASKIE_HAJNOWSKI_BIALOWIEZA_WIEJSKA = ('2005022', 'Białowieża', GminaType.WIEJSKA, 'podlaskie', 'hajnowski',
                                              'powiat')
    PODLASKIE_HAJNOWSKI_CZEREMCHA_WIEJSKA = ('2005032', 'Czeremcha', GminaType.WIEJSKA, 'podlaskie', 'hajnowski',
                                             'powiat')
    PODLASKIE_HAJNOWSKI_CZYZE_WIEJSKA = ('2005042', 'Czyże', GminaType.WIEJSKA, 'podlaskie', 'hajnowski', 'powiat')
    PODLASKIE_HAJNOWSKI_DUBICZE_CERKIEWNE_WIEJSKA = ('2005052', 'Dubicze Cerkiewne', GminaType.WIEJSKA, 'podlaskie',
                                                     'hajnowski', 'powiat')
    PODLASKIE_HAJNOWSKI_HAJNOWKA_WIEJSKA = ('2005062', 'Hajnówka', GminaType.WIEJSKA, 'podlaskie', 'hajnowski',
                                            'powiat')
    PODLASKIE_HAJNOWSKI_KLESZCZELE_MIEJSKO_WIEJSKA = ('2005073', 'Kleszczele', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                      'hajnowski', 'powiat')
    PODLASKIE_HAJNOWSKI_NAREW_WIEJSKA = ('2005082', 'Narew', GminaType.WIEJSKA, 'podlaskie', 'hajnowski', 'powiat')
    PODLASKIE_HAJNOWSKI_NAREWKA_WIEJSKA = ('2005092', 'Narewka', GminaType.WIEJSKA, 'podlaskie', 'hajnowski', 'powiat')
    PODLASKIE_KOLNENSKI_KOLNO_MIEJSKA = ('2006011', 'Kolno', GminaType.MIEJSKA, 'podlaskie', 'kolneński', 'powiat')
    PODLASKIE_KOLNENSKI_GRABOWO_WIEJSKA = ('2006022', 'Grabowo', GminaType.WIEJSKA, 'podlaskie', 'kolneński', 'powiat')
    PODLASKIE_KOLNENSKI_KOLNO_WIEJSKA = ('2006032', 'Kolno', GminaType.WIEJSKA, 'podlaskie', 'kolneński', 'powiat')
    PODLASKIE_KOLNENSKI_MALY_PLOCK_WIEJSKA = ('2006042', 'Mały Płock', GminaType.WIEJSKA, 'podlaskie', 'kolneński',
                                              'powiat')
    PODLASKIE_KOLNENSKI_STAWISKI_MIEJSKO_WIEJSKA = ('2006053', 'Stawiski', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                    'kolneński', 'powiat')
    PODLASKIE_KOLNENSKI_TUROSL_WIEJSKA = ('2006062', 'Turośl', GminaType.WIEJSKA, 'podlaskie', 'kolneński', 'powiat')
    PODLASKIE_LOMZYNSKI_JEDWABNE_MIEJSKO_WIEJSKA = ('2007013', 'Jedwabne', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                    'łomżyński', 'powiat')
    PODLASKIE_LOMZYNSKI_LOMZA_WIEJSKA = ('2007022', 'Łomża', GminaType.WIEJSKA, 'podlaskie', 'łomżyński', 'powiat')
    PODLASKIE_LOMZYNSKI_MIASTKOWO_WIEJSKA = ('2007032', 'Miastkowo', GminaType.WIEJSKA, 'podlaskie', 'łomżyński',
                                             'powiat')
    PODLASKIE_LOMZYNSKI_NOWOGROD_MIEJSKO_WIEJSKA = ('2007043', 'Nowogród', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                    'łomżyński', 'powiat')
    PODLASKIE_LOMZYNSKI_PIATNICA_WIEJSKA = ('2007052', 'Piątnica', GminaType.WIEJSKA, 'podlaskie', 'łomżyński',
                                            'powiat')
    PODLASKIE_LOMZYNSKI_PRZYTULY_WIEJSKA = ('2007062', 'Przytuły', GminaType.WIEJSKA, 'podlaskie', 'łomżyński',
                                            'powiat')
    PODLASKIE_LOMZYNSKI_SNIADOWO_WIEJSKA = ('2007072', 'Śniadowo', GminaType.WIEJSKA, 'podlaskie', 'łomżyński',
                                            'powiat')
    PODLASKIE_LOMZYNSKI_WIZNA_WIEJSKA = ('2007082', 'Wizna', GminaType.WIEJSKA, 'podlaskie', 'łomżyński', 'powiat')
    PODLASKIE_LOMZYNSKI_ZBOJNA_WIEJSKA = ('2007092', 'Zbójna', GminaType.WIEJSKA, 'podlaskie', 'łomżyński', 'powiat')
    PODLASKIE_MONIECKI_GONIADZ_MIEJSKO_WIEJSKA = ('2008013', 'Goniądz', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                  'moniecki', 'powiat')
    PODLASKIE_MONIECKI_JASIONOWKA_WIEJSKA = ('2008022', 'Jasionówka', GminaType.WIEJSKA, 'podlaskie', 'moniecki',
                                             'powiat')
    PODLASKIE_MONIECKI_JASWILY_WIEJSKA = ('2008032', 'Jaświły', GminaType.WIEJSKA, 'podlaskie', 'moniecki', 'powiat')
    PODLASKIE_MONIECKI_KNYSZYN_MIEJSKO_WIEJSKA = ('2008043', 'Knyszyn', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                  'moniecki', 'powiat')
    PODLASKIE_MONIECKI_KRYPNO_WIEJSKA = ('2008052', 'Krypno', GminaType.WIEJSKA, 'podlaskie', 'moniecki', 'powiat')
    PODLASKIE_MONIECKI_MONKI_MIEJSKO_WIEJSKA = ('2008063', 'Mońki', GminaType.MIEJSKO_WIEJSKA, 'podlaskie', 'moniecki',
                                                'powiat')
    PODLASKIE_MONIECKI_TRZCIANNE_WIEJSKA = ('2008072', 'Trzcianne', GminaType.WIEJSKA, 'podlaskie', 'moniecki',
                                            'powiat')
    PODLASKIE_SEJNENSKI_SEJNY_MIEJSKA = ('2009011', 'Sejny', GminaType.MIEJSKA, 'podlaskie', 'sejneński', 'powiat')
    PODLASKIE_SEJNENSKI_GIBY_WIEJSKA = ('2009022', 'Giby', GminaType.WIEJSKA, 'podlaskie', 'sejneński', 'powiat')
    PODLASKIE_SEJNENSKI_KRASNOPOL_WIEJSKA = ('2009032', 'Krasnopol', GminaType.WIEJSKA, 'podlaskie', 'sejneński',
                                             'powiat')
    PODLASKIE_SEJNENSKI_PUNSK_WIEJSKA = ('2009042', 'Puńsk', GminaType.WIEJSKA, 'podlaskie', 'sejneński', 'powiat')
    PODLASKIE_SEJNENSKI_SEJNY_WIEJSKA = ('2009052', 'Sejny', GminaType.WIEJSKA, 'podlaskie', 'sejneński', 'powiat')
    PODLASKIE_SIEMIATYCKI_SIEMIATYCZE_MIEJSKA = ('2010011', 'Siemiatycze', GminaType.MIEJSKA, 'podlaskie',
                                                 'siemiatycki', 'powiat')
    PODLASKIE_SIEMIATYCKI_DROHICZYN_MIEJSKO_WIEJSKA = ('2010023', 'Drohiczyn', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                       'siemiatycki', 'powiat')
    PODLASKIE_SIEMIATYCKI_DZIADKOWICE_WIEJSKA = ('2010032', 'Dziadkowice', GminaType.WIEJSKA, 'podlaskie',
                                                 'siemiatycki', 'powiat')
    PODLASKIE_SIEMIATYCKI_GRODZISK_WIEJSKA = ('2010042', 'Grodzisk', GminaType.WIEJSKA, 'podlaskie', 'siemiatycki',
                                              'powiat')
    PODLASKIE_SIEMIATYCKI_MIELNIK_WIEJSKA = ('2010052', 'Mielnik', GminaType.WIEJSKA, 'podlaskie', 'siemiatycki',
                                             'powiat')
    PODLASKIE_SIEMIATYCKI_MILEJCZYCE_WIEJSKA = ('2010062', 'Milejczyce', GminaType.WIEJSKA, 'podlaskie', 'siemiatycki',
                                                'powiat')
    PODLASKIE_SIEMIATYCKI_NURZEC_STACJA_WIEJSKA = ('2010072', 'Nurzec-Stacja', GminaType.WIEJSKA, 'podlaskie',
                                                   'siemiatycki', 'powiat')
    PODLASKIE_SIEMIATYCKI_PERLEJEWO_WIEJSKA = ('2010082', 'Perlejewo', GminaType.WIEJSKA, 'podlaskie', 'siemiatycki',
                                               'powiat')
    PODLASKIE_SIEMIATYCKI_SIEMIATYCZE_WIEJSKA = ('2010092', 'Siemiatycze', GminaType.WIEJSKA, 'podlaskie',
                                                 'siemiatycki', 'powiat')
    PODLASKIE_SOKOLSKI_DABROWA_BIALOSTOCKA_MIEJSKO_WIEJSKA = ('2011013', 'Dąbrowa Białostocka',
                                                              GminaType.MIEJSKO_WIEJSKA, 'podlaskie', 'sokólski',
                                                              'powiat')
    PODLASKIE_SOKOLSKI_JANOW_WIEJSKA = ('2011022', 'Janów', GminaType.WIEJSKA, 'podlaskie', 'sokólski', 'powiat')
    PODLASKIE_SOKOLSKI_KORYCIN_WIEJSKA = ('2011032', 'Korycin', GminaType.WIEJSKA, 'podlaskie', 'sokólski', 'powiat')
    PODLASKIE_SOKOLSKI_KRYNKI_MIEJSKO_WIEJSKA = ('2011043', 'Krynki', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                 'sokólski', 'powiat')
    PODLASKIE_SOKOLSKI_KUZNICA_WIEJSKA = ('2011052', 'Kuźnica', GminaType.WIEJSKA, 'podlaskie', 'sokólski', 'powiat')
    PODLASKIE_SOKOLSKI_NOWY_DWOR_WIEJSKA = ('2011062', 'Nowy Dwór', GminaType.WIEJSKA, 'podlaskie', 'sokólski',
                                            'powiat')
    PODLASKIE_SOKOLSKI_SIDRA_WIEJSKA = ('2011072', 'Sidra', GminaType.WIEJSKA, 'podlaskie', 'sokólski', 'powiat')
    PODLASKIE_SOKOLSKI_SOKOLKA_MIEJSKO_WIEJSKA = ('2011083', 'Sokółka', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                  'sokólski', 'powiat')
    PODLASKIE_SOKOLSKI_SUCHOWOLA_MIEJSKO_WIEJSKA = ('2011093', 'Suchowola', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                    'sokólski', 'powiat')
    PODLASKIE_SOKOLSKI_SZUDZIALOWO_WIEJSKA = ('2011102', 'Szudziałowo', GminaType.WIEJSKA, 'podlaskie', 'sokólski',
                                              'powiat')
    PODLASKIE_SUWALSKI_BAKALARZEWO_WIEJSKA = ('2012012', 'Bakałarzewo', GminaType.WIEJSKA, 'podlaskie', 'suwalski',
                                              'powiat')
    PODLASKIE_SUWALSKI_FILIPOW_WIEJSKA = ('2012022', 'Filipów', GminaType.WIEJSKA, 'podlaskie', 'suwalski', 'powiat')
    PODLASKIE_SUWALSKI_JELENIEWO_WIEJSKA = ('2012032', 'Jeleniewo', GminaType.WIEJSKA, 'podlaskie', 'suwalski',
                                            'powiat')
    PODLASKIE_SUWALSKI_PRZEROSL_WIEJSKA = ('2012042', 'Przerośl', GminaType.WIEJSKA, 'podlaskie', 'suwalski', 'powiat')
    PODLASKIE_SUWALSKI_RACZKI_WIEJSKA = ('2012052', 'Raczki', GminaType.WIEJSKA, 'podlaskie', 'suwalski', 'powiat')
    PODLASKIE_SUWALSKI_RUTKA_TARTAK_WIEJSKA = ('2012062', 'Rutka-Tartak', GminaType.WIEJSKA, 'podlaskie', 'suwalski',
                                               'powiat')
    PODLASKIE_SUWALSKI_SUWALKI_WIEJSKA = ('2012072', 'Suwałki', GminaType.WIEJSKA, 'podlaskie', 'suwalski', 'powiat')
    PODLASKIE_SUWALSKI_SZYPLISZKI_WIEJSKA = ('2012082', 'Szypliszki', GminaType.WIEJSKA, 'podlaskie', 'suwalski',
                                             'powiat')
    PODLASKIE_SUWALSKI_WIZAJNY_WIEJSKA = ('2012092', 'Wiżajny', GminaType.WIEJSKA, 'podlaskie', 'suwalski', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_WYSOKIE_MAZOWIECKIE_MIEJSKA = ('2013011', 'Wysokie Mazowieckie', GminaType.MIEJSKA,
                                                              'podlaskie', 'wysokomazowiecki', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_CIECHANOWIEC_MIEJSKO_WIEJSKA = ('2013023', 'Ciechanowiec', GminaType.MIEJSKO_WIEJSKA,
                                                               'podlaskie', 'wysokomazowiecki', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_CZYZEW_MIEJSKO_WIEJSKA = ('2013033', 'Czyżew', GminaType.MIEJSKO_WIEJSKA, 'podlaskie',
                                                         'wysokomazowiecki', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_KLUKOWO_WIEJSKA = ('2013042', 'Klukowo', GminaType.WIEJSKA, 'podlaskie',
                                                  'wysokomazowiecki', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_KOBYLIN_BORZYMY_WIEJSKA = ('2013052', 'Kobylin-Borzymy', GminaType.WIEJSKA, 'podlaskie',
                                                          'wysokomazowiecki', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_KULESZE_KOSCIELNE_WIEJSKA = ('2013062', 'Kulesze Kościelne', GminaType.WIEJSKA,
                                                            'podlaskie', 'wysokomazowiecki', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_NOWE_PIEKUTY_WIEJSKA = ('2013072', 'Nowe Piekuty', GminaType.WIEJSKA, 'podlaskie',
                                                       'wysokomazowiecki', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_SOKOLY_WIEJSKA = ('2013082', 'Sokoły', GminaType.WIEJSKA, 'podlaskie',
                                                 'wysokomazowiecki', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_SZEPIETOWO_MIEJSKO_WIEJSKA = ('2013093', 'Szepietowo', GminaType.MIEJSKO_WIEJSKA,
                                                             'podlaskie', 'wysokomazowiecki', 'powiat')
    PODLASKIE_WYSOKOMAZOWIECKI_WYSOKIE_MAZOWIECKIE_WIEJSKA = ('2013102', 'Wysokie Mazowieckie', GminaType.WIEJSKA,
                                                              'podlaskie', 'wysokomazowiecki', 'powiat')
    PODLASKIE_ZAMBROWSKI_ZAMBROW_MIEJSKA = ('2014011', 'Zambrów', GminaType.MIEJSKA, 'podlaskie', 'zambrowski',
                                            'powiat')
    PODLASKIE_ZAMBROWSKI_KOLAKI_KOSCIELNE_WIEJSKA = ('2014022', 'Kołaki Kościelne', GminaType.WIEJSKA, 'podlaskie',
                                                     'zambrowski', 'powiat')
    PODLASKIE_ZAMBROWSKI_RUTKI_WIEJSKA = ('2014032', 'Rutki', GminaType.WIEJSKA, 'podlaskie', 'zambrowski', 'powiat')
    PODLASKIE_ZAMBROWSKI_SZUMOWO_WIEJSKA = ('2014042', 'Szumowo', GminaType.WIEJSKA, 'podlaskie', 'zambrowski',
                                            'powiat')
    PODLASKIE_ZAMBROWSKI_ZAMBROW_WIEJSKA = ('2014052', 'Zambrów', GminaType.WIEJSKA, 'podlaskie', 'zambrowski',
                                            'powiat')
    PODLASKIE_BIALYSTOK_BIALYSTOK_MIEJSKA = ('2061011', 'Białystok', GminaType.MIEJSKA, 'podlaskie', 'Białystok',
                                             'miasto na prawach powiatu')
    PODLASKIE_LOMZA_LOMZA_MIEJSKA = ('2062011', 'Łomża', GminaType.MIEJSKA, 'podlaskie', 'Łomża',
                                     'miasto na prawach powiatu')
    PODLASKIE_SUWALKI_SUWALKI_MIEJSKA = ('2063011', 'Suwałki', GminaType.MIEJSKA, 'podlaskie', 'Suwałki',
                                         'miasto na prawach powiatu')

    # Pomorskie
    POMORSKIE_BYTOWSKI_BORZYTUCHOM_WIEJSKA = ('2201012', 'Borzytuchom', GminaType.WIEJSKA, 'pomorskie', 'bytowski',
                                              'powiat')
    POMORSKIE_BYTOWSKI_BYTOW_MIEJSKO_WIEJSKA = ('2201023', 'Bytów', GminaType.MIEJSKO_WIEJSKA, 'pomorskie', 'bytowski',
                                                'powiat')
    POMORSKIE_BYTOWSKI_CZARNA_DABROWKA_WIEJSKA = ('2201032', 'Czarna Dąbrówka', GminaType.WIEJSKA, 'pomorskie',
                                                  'bytowski', 'powiat')
    POMORSKIE_BYTOWSKI_KOLCZYGLOWY_WIEJSKA = ('2201042', 'Kołczygłowy', GminaType.WIEJSKA, 'pomorskie', 'bytowski',
                                              'powiat')
    POMORSKIE_BYTOWSKI_LIPNICA_WIEJSKA = ('2201052', 'Lipnica', GminaType.WIEJSKA, 'pomorskie', 'bytowski', 'powiat')
    POMORSKIE_BYTOWSKI_MIASTKO_MIEJSKO_WIEJSKA = ('2201063', 'Miastko', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                  'bytowski', 'powiat')
    POMORSKIE_BYTOWSKI_PARCHOWO_WIEJSKA = ('2201072', 'Parchowo', GminaType.WIEJSKA, 'pomorskie', 'bytowski', 'powiat')
    POMORSKIE_BYTOWSKI_STUDZIENICE_WIEJSKA = ('2201082', 'Studzienice', GminaType.WIEJSKA, 'pomorskie', 'bytowski',
                                              'powiat')
    POMORSKIE_BYTOWSKI_TRZEBIELINO_WIEJSKA = ('2201092', 'Trzebielino', GminaType.WIEJSKA, 'pomorskie', 'bytowski',
                                              'powiat')
    POMORSKIE_BYTOWSKI_TUCHOMIE_WIEJSKA = ('2201102', 'Tuchomie', GminaType.WIEJSKA, 'pomorskie', 'bytowski', 'powiat')
    POMORSKIE_CHOJNICKI_CHOJNICE_MIEJSKA = ('2202011', 'Chojnice', GminaType.MIEJSKA, 'pomorskie', 'chojnicki',
                                            'powiat')
    POMORSKIE_CHOJNICKI_BRUSY_MIEJSKO_WIEJSKA = ('2202023', 'Brusy', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                 'chojnicki', 'powiat')
    POMORSKIE_CHOJNICKI_CHOJNICE_WIEJSKA = ('2202032', 'Chojnice', GminaType.WIEJSKA, 'pomorskie', 'chojnicki',
                                            'powiat')
    POMORSKIE_CHOJNICKI_CZERSK_MIEJSKO_WIEJSKA = ('2202043', 'Czersk', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                  'chojnicki', 'powiat')
    POMORSKIE_CHOJNICKI_KONARZYNY_WIEJSKA = ('2202052', 'Konarzyny', GminaType.WIEJSKA, 'pomorskie', 'chojnicki',
                                             'powiat')
    POMORSKIE_CZLUCHOWSKI_CZLUCHOW_MIEJSKA = ('2203011', 'Człuchów', GminaType.MIEJSKA, 'pomorskie', 'człuchowski',
                                              'powiat')
    POMORSKIE_CZLUCHOWSKI_CZARNE_MIEJSKO_WIEJSKA = ('2203023', 'Czarne', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                    'człuchowski', 'powiat')
    POMORSKIE_CZLUCHOWSKI_CZLUCHOW_WIEJSKA = ('2203032', 'Człuchów', GminaType.WIEJSKA, 'pomorskie', 'człuchowski',
                                              'powiat')
    POMORSKIE_CZLUCHOWSKI_DEBRZNO_MIEJSKO_WIEJSKA = ('2203043', 'Debrzno', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                     'człuchowski', 'powiat')
    POMORSKIE_CZLUCHOWSKI_KOCZALA_WIEJSKA = ('2203052', 'Koczała', GminaType.WIEJSKA, 'pomorskie', 'człuchowski',
                                             'powiat')
    POMORSKIE_CZLUCHOWSKI_PRZECHLEWO_WIEJSKA = ('2203062', 'Przechlewo', GminaType.WIEJSKA, 'pomorskie', 'człuchowski',
                                                'powiat')
    POMORSKIE_CZLUCHOWSKI_RZECZENICA_WIEJSKA = ('2203072', 'Rzeczenica', GminaType.WIEJSKA, 'pomorskie', 'człuchowski',
                                                'powiat')
    POMORSKIE_GDANSKI_PRUSZCZ_GDANSKI_MIEJSKA = ('2204011', 'Pruszcz Gdański', GminaType.MIEJSKA, 'pomorskie',
                                                 'gdański', 'powiat')
    POMORSKIE_GDANSKI_CEDRY_WIELKIE_WIEJSKA = ('2204022', 'Cedry Wielkie', GminaType.WIEJSKA, 'pomorskie', 'gdański',
                                               'powiat')
    POMORSKIE_GDANSKI_KOLBUDY_WIEJSKA = ('2204032', 'Kolbudy', GminaType.WIEJSKA, 'pomorskie', 'gdański', 'powiat')
    POMORSKIE_GDANSKI_PRUSZCZ_GDANSKI_WIEJSKA = ('2204042', 'Pruszcz Gdański', GminaType.WIEJSKA, 'pomorskie',
                                                 'gdański', 'powiat')
    POMORSKIE_GDANSKI_PRZYWIDZ_WIEJSKA = ('2204052', 'Przywidz', GminaType.WIEJSKA, 'pomorskie', 'gdański', 'powiat')
    POMORSKIE_GDANSKI_PSZCZOLKI_WIEJSKA = ('2204062', 'Pszczółki', GminaType.WIEJSKA, 'pomorskie', 'gdański', 'powiat')
    POMORSKIE_GDANSKI_SUCHY_DAB_WIEJSKA = ('2204072', 'Suchy Dąb', GminaType.WIEJSKA, 'pomorskie', 'gdański', 'powiat')
    POMORSKIE_GDANSKI_TRABKI_WIELKIE_WIEJSKA = ('2204082', 'Trąbki Wielkie', GminaType.WIEJSKA, 'pomorskie', 'gdański',
                                                'powiat')
    POMORSKIE_KARTUSKI_CHMIELNO_WIEJSKA = ('2205012', 'Chmielno', GminaType.WIEJSKA, 'pomorskie', 'kartuski', 'powiat')
    POMORSKIE_KARTUSKI_KARTUZY_MIEJSKO_WIEJSKA = ('2205023', 'Kartuzy', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                  'kartuski', 'powiat')
    POMORSKIE_KARTUSKI_PRZODKOWO_WIEJSKA = ('2205032', 'Przodkowo', GminaType.WIEJSKA, 'pomorskie', 'kartuski',
                                            'powiat')
    POMORSKIE_KARTUSKI_SIERAKOWICE_WIEJSKA = ('2205042', 'Sierakowice', GminaType.WIEJSKA, 'pomorskie', 'kartuski',
                                              'powiat')
    POMORSKIE_KARTUSKI_SOMONINO_WIEJSKA = ('2205052', 'Somonino', GminaType.WIEJSKA, 'pomorskie', 'kartuski', 'powiat')
    POMORSKIE_KARTUSKI_STEZYCA_WIEJSKA = ('2205062', 'Stężyca', GminaType.WIEJSKA, 'pomorskie', 'kartuski', 'powiat')
    POMORSKIE_KARTUSKI_SULECZYNO_WIEJSKA = ('2205072', 'Sulęczyno', GminaType.WIEJSKA, 'pomorskie', 'kartuski',
                                            'powiat')
    POMORSKIE_KARTUSKI_ZUKOWO_MIEJSKO_WIEJSKA = ('2205083', 'Żukowo', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                 'kartuski', 'powiat')
    POMORSKIE_KOSCIERSKI_KOSCIERZYNA_MIEJSKA = ('2206011', 'Kościerzyna', GminaType.MIEJSKA, 'pomorskie', 'kościerski',
                                                'powiat')
    POMORSKIE_KOSCIERSKI_DZIEMIANY_WIEJSKA = ('2206022', 'Dziemiany', GminaType.WIEJSKA, 'pomorskie', 'kościerski',
                                              'powiat')
    POMORSKIE_KOSCIERSKI_KARSIN_WIEJSKA = ('2206032', 'Karsin', GminaType.WIEJSKA, 'pomorskie', 'kościerski', 'powiat')
    POMORSKIE_KOSCIERSKI_KOSCIERZYNA_WIEJSKA = ('2206042', 'Kościerzyna', GminaType.WIEJSKA, 'pomorskie', 'kościerski',
                                                'powiat')
    POMORSKIE_KOSCIERSKI_LINIEWO_WIEJSKA = ('2206052', 'Liniewo', GminaType.WIEJSKA, 'pomorskie', 'kościerski',
                                            'powiat')
    POMORSKIE_KOSCIERSKI_LIPUSZ_WIEJSKA = ('2206062', 'Lipusz', GminaType.WIEJSKA, 'pomorskie', 'kościerski', 'powiat')
    POMORSKIE_KOSCIERSKI_NOWA_KARCZMA_WIEJSKA = ('2206072', 'Nowa Karczma', GminaType.WIEJSKA, 'pomorskie',
                                                 'kościerski', 'powiat')
    POMORSKIE_KOSCIERSKI_STARA_KISZEWA_WIEJSKA = ('2206082', 'Stara Kiszewa', GminaType.WIEJSKA, 'pomorskie',
                                                  'kościerski', 'powiat')
    POMORSKIE_KWIDZYNSKI_KWIDZYN_MIEJSKA = ('2207011', 'Kwidzyn', GminaType.MIEJSKA, 'pomorskie', 'kwidzyński',
                                            'powiat')
    POMORSKIE_KWIDZYNSKI_GARDEJA_WIEJSKA = ('2207022', 'Gardeja', GminaType.WIEJSKA, 'pomorskie', 'kwidzyński',
                                            'powiat')
    POMORSKIE_KWIDZYNSKI_KWIDZYN_WIEJSKA = ('2207032', 'Kwidzyn', GminaType.WIEJSKA, 'pomorskie', 'kwidzyński',
                                            'powiat')
    POMORSKIE_KWIDZYNSKI_PRABUTY_MIEJSKO_WIEJSKA = ('2207043', 'Prabuty', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                    'kwidzyński', 'powiat')
    POMORSKIE_KWIDZYNSKI_RYJEWO_WIEJSKA = ('2207052', 'Ryjewo', GminaType.WIEJSKA, 'pomorskie', 'kwidzyński', 'powiat')
    POMORSKIE_KWIDZYNSKI_SADLINKI_WIEJSKA = ('2207062', 'Sadlinki', GminaType.WIEJSKA, 'pomorskie', 'kwidzyński',
                                             'powiat')
    POMORSKIE_LEBORSKI_LEBORK_MIEJSKA = ('2208011', 'Lębork', GminaType.MIEJSKA, 'pomorskie', 'lęborski', 'powiat')
    POMORSKIE_LEBORSKI_LEBA_MIEJSKA = ('2208021', 'Łeba', GminaType.MIEJSKA, 'pomorskie', 'lęborski', 'powiat')
    POMORSKIE_LEBORSKI_CEWICE_WIEJSKA = ('2208032', 'Cewice', GminaType.WIEJSKA, 'pomorskie', 'lęborski', 'powiat')
    POMORSKIE_LEBORSKI_NOWA_WIES_LEBORSKA_WIEJSKA = ('2208042', 'Nowa Wieś Lęborska', GminaType.WIEJSKA, 'pomorskie',
                                                     'lęborski', 'powiat')
    POMORSKIE_LEBORSKI_WICKO_WIEJSKA = ('2208052', 'Wicko', GminaType.WIEJSKA, 'pomorskie', 'lęborski', 'powiat')
    POMORSKIE_MALBORSKI_MALBORK_MIEJSKA = ('2209011', 'Malbork', GminaType.MIEJSKA, 'pomorskie', 'malborski', 'powiat')
    POMORSKIE_MALBORSKI_LICHNOWY_WIEJSKA = ('2209032', 'Lichnowy', GminaType.WIEJSKA, 'pomorskie', 'malborski',
                                            'powiat')
    POMORSKIE_MALBORSKI_MALBORK_WIEJSKA = ('2209042', 'Malbork', GminaType.WIEJSKA, 'pomorskie', 'malborski', 'powiat')
    POMORSKIE_MALBORSKI_MILORADZ_WIEJSKA = ('2209062', 'Miłoradz', GminaType.WIEJSKA, 'pomorskie', 'malborski',
                                            'powiat')
    POMORSKIE_MALBORSKI_NOWY_STAW_MIEJSKO_WIEJSKA = ('2209073', 'Nowy Staw', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                     'malborski', 'powiat')
    POMORSKIE_MALBORSKI_STARE_POLE_WIEJSKA = ('2209082', 'Stare Pole', GminaType.WIEJSKA, 'pomorskie', 'malborski',
                                              'powiat')
    POMORSKIE_NOWODWORSKI_KRYNICA_MORSKA_MIEJSKA = ('2210011', 'Krynica Morska', GminaType.MIEJSKA, 'pomorskie',
                                                    'nowodworski', 'powiat')
    POMORSKIE_NOWODWORSKI_NOWY_DWOR_GDANSKI_MIEJSKO_WIEJSKA = ('2210023', 'Nowy Dwór Gdański',
                                                               GminaType.MIEJSKO_WIEJSKA, 'pomorskie', 'nowodworski',
                                                               'powiat')
    POMORSKIE_NOWODWORSKI_OSTASZEWO_WIEJSKA = ('2210032', 'Ostaszewo', GminaType.WIEJSKA, 'pomorskie', 'nowodworski',
                                               'powiat')
    POMORSKIE_NOWODWORSKI_STEGNA_WIEJSKA = ('2210042', 'Stegna', GminaType.WIEJSKA, 'pomorskie', 'nowodworski',
                                            'powiat')
    POMORSKIE_NOWODWORSKI_SZTUTOWO_WIEJSKA = ('2210052', 'Sztutowo', GminaType.WIEJSKA, 'pomorskie', 'nowodworski',
                                              'powiat')
    POMORSKIE_PUCKI_HEL_MIEJSKA = ('2211011', 'Hel', GminaType.MIEJSKA, 'pomorskie', 'pucki', 'powiat')
    POMORSKIE_PUCKI_JASTARNIA_MIEJSKO_WIEJSKA = ('2211023', 'Jastarnia', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                 'pucki', 'powiat')
    POMORSKIE_PUCKI_PUCK_MIEJSKA = ('2211031', 'Puck', GminaType.MIEJSKA, 'pomorskie', 'pucki', 'powiat')
    POMORSKIE_PUCKI_WLADYSLAWOWO_MIEJSKO_WIEJSKA = ('2211043', 'Władysławowo', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                    'pucki', 'powiat')
    POMORSKIE_PUCKI_KOSAKOWO_WIEJSKA = ('2211052', 'Kosakowo', GminaType.WIEJSKA, 'pomorskie', 'pucki', 'powiat')
    POMORSKIE_PUCKI_KROKOWA_WIEJSKA = ('2211062', 'Krokowa', GminaType.WIEJSKA, 'pomorskie', 'pucki', 'powiat')
    POMORSKIE_PUCKI_PUCK_WIEJSKA = ('2211072', 'Puck', GminaType.WIEJSKA, 'pomorskie', 'pucki', 'powiat')
    POMORSKIE_SLUPSKI_USTKA_MIEJSKA = ('2212011', 'Ustka', GminaType.MIEJSKA, 'pomorskie', 'słupski', 'powiat')
    POMORSKIE_SLUPSKI_DAMNICA_WIEJSKA = ('2212022', 'Damnica', GminaType.WIEJSKA, 'pomorskie', 'słupski', 'powiat')
    POMORSKIE_SLUPSKI_DEBNICA_KASZUBSKA_WIEJSKA = ('2212032', 'Dębnica Kaszubska', GminaType.WIEJSKA, 'pomorskie',
                                                   'słupski', 'powiat')
    POMORSKIE_SLUPSKI_GLOWCZYCE_WIEJSKA = ('2212042', 'Główczyce', GminaType.WIEJSKA, 'pomorskie', 'słupski', 'powiat')
    POMORSKIE_SLUPSKI_KEPICE_MIEJSKO_WIEJSKA = ('2212053', 'Kępice', GminaType.MIEJSKO_WIEJSKA, 'pomorskie', 'słupski',
                                                'powiat')
    POMORSKIE_SLUPSKI_KOBYLNICA_MIEJSKO_WIEJSKA = ('2212063', 'Kobylnica', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                   'słupski', 'powiat')
    POMORSKIE_SLUPSKI_POTEGOWO_WIEJSKA = ('2212072', 'Potęgowo', GminaType.WIEJSKA, 'pomorskie', 'słupski', 'powiat')
    POMORSKIE_SLUPSKI_REDZIKOWO_WIEJSKA = ('2212082', 'Redzikowo', GminaType.WIEJSKA, 'pomorskie', 'słupski', 'powiat')
    POMORSKIE_SLUPSKI_SMOLDZINO_WIEJSKA = ('2212092', 'Smołdzino', GminaType.WIEJSKA, 'pomorskie', 'słupski', 'powiat')
    POMORSKIE_SLUPSKI_USTKA_WIEJSKA = ('2212102', 'Ustka', GminaType.WIEJSKA, 'pomorskie', 'słupski', 'powiat')
    POMORSKIE_STAROGARDZKI_CZARNA_WODA_MIEJSKO_WIEJSKA = ('2213013', 'Czarna Woda', GminaType.MIEJSKO_WIEJSKA,
                                                          'pomorskie', 'starogardzki', 'powiat')
    POMORSKIE_STAROGARDZKI_SKORCZ_MIEJSKA = ('2213021', 'Skórcz', GminaType.MIEJSKA, 'pomorskie', 'starogardzki',
                                             'powiat')
    POMORSKIE_STAROGARDZKI_STAROGARD_GDANSKI_MIEJSKA = ('2213031', 'Starogard Gdański', GminaType.MIEJSKA, 'pomorskie',
                                                        'starogardzki', 'powiat')
    POMORSKIE_STAROGARDZKI_BOBOWO_WIEJSKA = ('2213042', 'Bobowo', GminaType.WIEJSKA, 'pomorskie', 'starogardzki',
                                             'powiat')
    POMORSKIE_STAROGARDZKI_KALISKA_WIEJSKA = ('2213052', 'Kaliska', GminaType.WIEJSKA, 'pomorskie', 'starogardzki',
                                              'powiat')
    POMORSKIE_STAROGARDZKI_LUBICHOWO_WIEJSKA = ('2213062', 'Lubichowo', GminaType.WIEJSKA, 'pomorskie', 'starogardzki',
                                                'powiat')
    POMORSKIE_STAROGARDZKI_OSIECZNA_WIEJSKA = ('2213072', 'Osieczna', GminaType.WIEJSKA, 'pomorskie', 'starogardzki',
                                               'powiat')
    POMORSKIE_STAROGARDZKI_OSIEK_WIEJSKA = ('2213082', 'Osiek', GminaType.WIEJSKA, 'pomorskie', 'starogardzki',
                                            'powiat')
    POMORSKIE_STAROGARDZKI_SKARSZEWY_MIEJSKO_WIEJSKA = ('2213093', 'Skarszewy', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                        'starogardzki', 'powiat')
    POMORSKIE_STAROGARDZKI_SKORCZ_WIEJSKA = ('2213102', 'Skórcz', GminaType.WIEJSKA, 'pomorskie', 'starogardzki',
                                             'powiat')
    POMORSKIE_STAROGARDZKI_SMETOWO_GRANICZNE_WIEJSKA = ('2213112', 'Smętowo Graniczne', GminaType.WIEJSKA, 'pomorskie',
                                                        'starogardzki', 'powiat')
    POMORSKIE_STAROGARDZKI_STAROGARD_GDANSKI_WIEJSKA = ('2213122', 'Starogard Gdański', GminaType.WIEJSKA, 'pomorskie',
                                                        'starogardzki', 'powiat')
    POMORSKIE_STAROGARDZKI_ZBLEWO_WIEJSKA = ('2213132', 'Zblewo', GminaType.WIEJSKA, 'pomorskie', 'starogardzki',
                                             'powiat')
    POMORSKIE_TCZEWSKI_TCZEW_MIEJSKA = ('2214011', 'Tczew', GminaType.MIEJSKA, 'pomorskie', 'tczewski', 'powiat')
    POMORSKIE_TCZEWSKI_GNIEW_MIEJSKO_WIEJSKA = ('2214023', 'Gniew', GminaType.MIEJSKO_WIEJSKA, 'pomorskie', 'tczewski',
                                                'powiat')
    POMORSKIE_TCZEWSKI_MORZESZCZYN_WIEJSKA = ('2214032', 'Morzeszczyn', GminaType.WIEJSKA, 'pomorskie', 'tczewski',
                                              'powiat')
    POMORSKIE_TCZEWSKI_PELPLIN_MIEJSKO_WIEJSKA = ('2214043', 'Pelplin', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                  'tczewski', 'powiat')
    POMORSKIE_TCZEWSKI_SUBKOWY_WIEJSKA = ('2214052', 'Subkowy', GminaType.WIEJSKA, 'pomorskie', 'tczewski', 'powiat')
    POMORSKIE_TCZEWSKI_TCZEW_WIEJSKA = ('2214062', 'Tczew', GminaType.WIEJSKA, 'pomorskie', 'tczewski', 'powiat')
    POMORSKIE_WEJHEROWSKI_REDA_MIEJSKA = ('2215011', 'Reda', GminaType.MIEJSKA, 'pomorskie', 'wejherowski', 'powiat')
    POMORSKIE_WEJHEROWSKI_RUMIA_MIEJSKA = ('2215021', 'Rumia', GminaType.MIEJSKA, 'pomorskie', 'wejherowski', 'powiat')
    POMORSKIE_WEJHEROWSKI_WEJHEROWO_MIEJSKA = ('2215031', 'Wejherowo', GminaType.MIEJSKA, 'pomorskie', 'wejherowski',
                                               'powiat')
    POMORSKIE_WEJHEROWSKI_CHOCZEWO_WIEJSKA = ('2215042', 'Choczewo', GminaType.WIEJSKA, 'pomorskie', 'wejherowski',
                                              'powiat')
    POMORSKIE_WEJHEROWSKI_GNIEWINO_WIEJSKA = ('2215052', 'Gniewino', GminaType.WIEJSKA, 'pomorskie', 'wejherowski',
                                              'powiat')
    POMORSKIE_WEJHEROWSKI_LINIA_WIEJSKA = ('2215062', 'Linia', GminaType.WIEJSKA, 'pomorskie', 'wejherowski', 'powiat')
    POMORSKIE_WEJHEROWSKI_LUZINO_WIEJSKA = ('2215072', 'Luzino', GminaType.WIEJSKA, 'pomorskie', 'wejherowski',
                                            'powiat')
    POMORSKIE_WEJHEROWSKI_LECZYCE_WIEJSKA = ('2215082', 'Łęczyce', GminaType.WIEJSKA, 'pomorskie', 'wejherowski',
                                             'powiat')
    POMORSKIE_WEJHEROWSKI_SZEMUD_WIEJSKA = ('2215092', 'Szemud', GminaType.WIEJSKA, 'pomorskie', 'wejherowski',
                                            'powiat')
    POMORSKIE_WEJHEROWSKI_WEJHEROWO_WIEJSKA = ('2215102', 'Wejherowo', GminaType.WIEJSKA, 'pomorskie', 'wejherowski',
                                               'powiat')
    POMORSKIE_SZTUMSKI_DZIERZGON_MIEJSKO_WIEJSKA = ('2216013', 'Dzierzgoń', GminaType.MIEJSKO_WIEJSKA, 'pomorskie',
                                                    'sztumski', 'powiat')
    POMORSKIE_SZTUMSKI_MIKOLAJKI_POMORSKIE_WIEJSKA = ('2216022', 'Mikołajki Pomorskie', GminaType.WIEJSKA, 'pomorskie',
                                                      'sztumski', 'powiat')
    POMORSKIE_SZTUMSKI_STARY_DZIERZGON_WIEJSKA = ('2216032', 'Stary Dzierzgoń', GminaType.WIEJSKA, 'pomorskie',
                                                  'sztumski', 'powiat')
    POMORSKIE_SZTUMSKI_STARY_TARG_WIEJSKA = ('2216042', 'Stary Targ', GminaType.WIEJSKA, 'pomorskie', 'sztumski',
                                             'powiat')
    POMORSKIE_SZTUMSKI_SZTUM_MIEJSKO_WIEJSKA = ('2216053', 'Sztum', GminaType.MIEJSKO_WIEJSKA, 'pomorskie', 'sztumski',
                                                'powiat')
    POMORSKIE_GDANSK_GDANSK_MIEJSKA = ('2261011', 'Gdańsk', GminaType.MIEJSKA, 'pomorskie', 'Gdańsk',
                                       'miasto na prawach powiatu')
    POMORSKIE_GDYNIA_GDYNIA_MIEJSKA = ('2262011', 'Gdynia', GminaType.MIEJSKA, 'pomorskie', 'Gdynia',
                                       'miasto na prawach powiatu')
    POMORSKIE_SLUPSK_SLUPSK_MIEJSKA = ('2263011', 'Słupsk', GminaType.MIEJSKA, 'pomorskie', 'Słupsk',
                                       'miasto na prawach powiatu')
    POMORSKIE_SOPOT_SOPOT_MIEJSKA = ('2264011', 'Sopot', GminaType.MIEJSKA, 'pomorskie', 'Sopot',
                                     'miasto na prawach powiatu')

    # Śląskie
    SLASKIE_BEDZINSKI_BEDZIN_MIEJSKA = ('2401011', 'Będzin', GminaType.MIEJSKA, 'śląskie', 'będziński', 'powiat')
    SLASKIE_BEDZINSKI_CZELADZ_MIEJSKA = ('2401021', 'Czeladź', GminaType.MIEJSKA, 'śląskie', 'będziński', 'powiat')
    SLASKIE_BEDZINSKI_WOJKOWICE_MIEJSKA = ('2401031', 'Wojkowice', GminaType.MIEJSKA, 'śląskie', 'będziński', 'powiat')
    SLASKIE_BEDZINSKI_BOBROWNIKI_WIEJSKA = ('2401042', 'Bobrowniki', GminaType.WIEJSKA, 'śląskie', 'będziński',
                                            'powiat')
    SLASKIE_BEDZINSKI_MIERZECICE_WIEJSKA = ('2401052', 'Mierzęcice', GminaType.WIEJSKA, 'śląskie', 'będziński',
                                            'powiat')
    SLASKIE_BEDZINSKI_PSARY_WIEJSKA = ('2401062', 'Psary', GminaType.WIEJSKA, 'śląskie', 'będziński', 'powiat')
    SLASKIE_BEDZINSKI_SIEWIERZ_MIEJSKO_WIEJSKA = ('2401073', 'Siewierz', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                  'będziński', 'powiat')
    SLASKIE_BEDZINSKI_SLAWKOW_MIEJSKA = ('2401081', 'Sławków', GminaType.MIEJSKA, 'śląskie', 'będziński', 'powiat')
    SLASKIE_BIELSKI_SZCZYRK_MIEJSKA = ('2402011', 'Szczyrk', GminaType.MIEJSKA, 'śląskie', 'bielski', 'powiat')
    SLASKIE_BIELSKI_BESTWINA_WIEJSKA = ('2402022', 'Bestwina', GminaType.WIEJSKA, 'śląskie', 'bielski', 'powiat')
    SLASKIE_BIELSKI_BUCZKOWICE_WIEJSKA = ('2402032', 'Buczkowice', GminaType.WIEJSKA, 'śląskie', 'bielski', 'powiat')
    SLASKIE_BIELSKI_CZECHOWICE_DZIEDZICE_MIEJSKO_WIEJSKA = ('2402043', 'Czechowice-Dziedzice',
                                                            GminaType.MIEJSKO_WIEJSKA, 'śląskie', 'bielski', 'powiat')
    SLASKIE_BIELSKI_JASIENICA_WIEJSKA = ('2402052', 'Jasienica', GminaType.WIEJSKA, 'śląskie', 'bielski', 'powiat')
    SLASKIE_BIELSKI_JAWORZE_WIEJSKA = ('2402062', 'Jaworze', GminaType.WIEJSKA, 'śląskie', 'bielski', 'powiat')
    SLASKIE_BIELSKI_KOZY_WIEJSKA = ('2402072', 'Kozy', GminaType.WIEJSKA, 'śląskie', 'bielski', 'powiat')
    SLASKIE_BIELSKI_PORABKA_WIEJSKA = ('2402082', 'Porąbka', GminaType.WIEJSKA, 'śląskie', 'bielski', 'powiat')
    SLASKIE_BIELSKI_WILAMOWICE_MIEJSKO_WIEJSKA = ('2402093', 'Wilamowice', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                  'bielski', 'powiat')
    SLASKIE_BIELSKI_WILKOWICE_WIEJSKA = ('2402102', 'Wilkowice', GminaType.WIEJSKA, 'śląskie', 'bielski', 'powiat')
    SLASKIE_CIESZYNSKI_CIESZYN_MIEJSKA = ('2403011', 'Cieszyn', GminaType.MIEJSKA, 'śląskie', 'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_USTRON_MIEJSKA = ('2403021', 'Ustroń', GminaType.MIEJSKA, 'śląskie', 'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_WISLA_MIEJSKA = ('2403031', 'Wisła', GminaType.MIEJSKA, 'śląskie', 'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_BRENNA_WIEJSKA = ('2403042', 'Brenna', GminaType.WIEJSKA, 'śląskie', 'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_CHYBIE_WIEJSKA = ('2403052', 'Chybie', GminaType.WIEJSKA, 'śląskie', 'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_DEBOWIEC_WIEJSKA = ('2403062', 'Dębowiec', GminaType.WIEJSKA, 'śląskie', 'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_GOLESZOW_WIEJSKA = ('2403072', 'Goleszów', GminaType.WIEJSKA, 'śląskie', 'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_HAZLACH_WIEJSKA = ('2403082', 'Hażlach', GminaType.WIEJSKA, 'śląskie', 'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_ISTEBNA_WIEJSKA = ('2403092', 'Istebna', GminaType.WIEJSKA, 'śląskie', 'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_SKOCZOW_MIEJSKO_WIEJSKA = ('2403103', 'Skoczów', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                  'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_STRUMIEN_MIEJSKO_WIEJSKA = ('2403113', 'Strumień', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                   'cieszyński', 'powiat')
    SLASKIE_CIESZYNSKI_ZEBRZYDOWICE_WIEJSKA = ('2403122', 'Zebrzydowice', GminaType.WIEJSKA, 'śląskie', 'cieszyński',
                                               'powiat')
    SLASKIE_CZESTOCHOWSKI_BLACHOWNIA_MIEJSKO_WIEJSKA = ('2404013', 'Blachownia', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                        'częstochowski', 'powiat')
    SLASKIE_CZESTOCHOWSKI_DABROWA_ZIELONA_WIEJSKA = ('2404022', 'Dąbrowa Zielona', GminaType.WIEJSKA, 'śląskie',
                                                     'częstochowski', 'powiat')
    SLASKIE_CZESTOCHOWSKI_JANOW_MIEJSKO_WIEJSKA = ('2404033', 'Janów', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                   'częstochowski', 'powiat')
    SLASKIE_CZESTOCHOWSKI_KAMIENICA_POLSKA_WIEJSKA = ('2404042', 'Kamienica Polska', GminaType.WIEJSKA, 'śląskie',
                                                      'częstochowski', 'powiat')
    SLASKIE_CZESTOCHOWSKI_KLOMNICE_WIEJSKA = ('2404052', 'Kłomnice', GminaType.WIEJSKA, 'śląskie', 'częstochowski',
                                              'powiat')
    SLASKIE_CZESTOCHOWSKI_KONIECPOL_MIEJSKO_WIEJSKA = ('2404063', 'Koniecpol', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                       'częstochowski', 'powiat')
    SLASKIE_CZESTOCHOWSKI_KONOPISKA_WIEJSKA = ('2404072', 'Konopiska', GminaType.WIEJSKA, 'śląskie', 'częstochowski',
                                               'powiat')
    SLASKIE_CZESTOCHOWSKI_KRUSZYNA_WIEJSKA = ('2404082', 'Kruszyna', GminaType.WIEJSKA, 'śląskie', 'częstochowski',
                                              'powiat')
    SLASKIE_CZESTOCHOWSKI_LELOW_WIEJSKA = ('2404092', 'Lelów', GminaType.WIEJSKA, 'śląskie', 'częstochowski', 'powiat')
    SLASKIE_CZESTOCHOWSKI_MSTOW_WIEJSKA = ('2404102', 'Mstów', GminaType.WIEJSKA, 'śląskie', 'częstochowski', 'powiat')
    SLASKIE_CZESTOCHOWSKI_MYKANOW_WIEJSKA = ('2404112', 'Mykanów', GminaType.WIEJSKA, 'śląskie', 'częstochowski',
                                             'powiat')
    SLASKIE_CZESTOCHOWSKI_OLSZTYN_MIEJSKO_WIEJSKA = ('2404123', 'Olsztyn', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                     'częstochowski', 'powiat')
    SLASKIE_CZESTOCHOWSKI_POCZESNA_WIEJSKA = ('2404132', 'Poczesna', GminaType.WIEJSKA, 'śląskie', 'częstochowski',
                                              'powiat')
    SLASKIE_CZESTOCHOWSKI_PRZYROW_MIEJSKO_WIEJSKA = ('2404143', 'Przyrów', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                     'częstochowski', 'powiat')
    SLASKIE_CZESTOCHOWSKI_REDZINY_WIEJSKA = ('2404152', 'Rędziny', GminaType.WIEJSKA, 'śląskie', 'częstochowski',
                                             'powiat')
    SLASKIE_CZESTOCHOWSKI_STARCZA_WIEJSKA = ('2404162', 'Starcza', GminaType.WIEJSKA, 'śląskie', 'częstochowski',
                                             'powiat')
    SLASKIE_GLIWICKI_KNUROW_MIEJSKA = ('2405011', 'Knurów', GminaType.MIEJSKA, 'śląskie', 'gliwicki', 'powiat')
    SLASKIE_GLIWICKI_PYSKOWICE_MIEJSKA = ('2405021', 'Pyskowice', GminaType.MIEJSKA, 'śląskie', 'gliwicki', 'powiat')
    SLASKIE_GLIWICKI_GIERALTOWICE_WIEJSKA = ('2405032', 'Gierałtowice', GminaType.WIEJSKA, 'śląskie', 'gliwicki',
                                             'powiat')
    SLASKIE_GLIWICKI_PILCHOWICE_WIEJSKA = ('2405042', 'Pilchowice', GminaType.WIEJSKA, 'śląskie', 'gliwicki', 'powiat')
    SLASKIE_GLIWICKI_RUDZINIEC_WIEJSKA = ('2405052', 'Rudziniec', GminaType.WIEJSKA, 'śląskie', 'gliwicki', 'powiat')
    SLASKIE_GLIWICKI_SOSNICOWICE_MIEJSKO_WIEJSKA = ('2405063', 'Sośnicowice', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                    'gliwicki', 'powiat')
    SLASKIE_GLIWICKI_TOSZEK_MIEJSKO_WIEJSKA = ('2405073', 'Toszek', GminaType.MIEJSKO_WIEJSKA, 'śląskie', 'gliwicki',
                                               'powiat')
    SLASKIE_GLIWICKI_WIELOWIES_WIEJSKA = ('2405082', 'Wielowieś', GminaType.WIEJSKA, 'śląskie', 'gliwicki', 'powiat')
    SLASKIE_KLOBUCKI_KLOBUCK_MIEJSKO_WIEJSKA = ('2406013', 'Kłobuck', GminaType.MIEJSKO_WIEJSKA, 'śląskie', 'kłobucki',
                                                'powiat')
    SLASKIE_KLOBUCKI_KRZEPICE_MIEJSKO_WIEJSKA = ('2406023', 'Krzepice', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                 'kłobucki', 'powiat')
    SLASKIE_KLOBUCKI_LIPIE_WIEJSKA = ('2406032', 'Lipie', GminaType.WIEJSKA, 'śląskie', 'kłobucki', 'powiat')
    SLASKIE_KLOBUCKI_MIEDZNO_WIEJSKA = ('2406042', 'Miedźno', GminaType.WIEJSKA, 'śląskie', 'kłobucki', 'powiat')
    SLASKIE_KLOBUCKI_OPATOW_WIEJSKA = ('2406052', 'Opatów', GminaType.WIEJSKA, 'śląskie', 'kłobucki', 'powiat')
    SLASKIE_KLOBUCKI_PANKI_WIEJSKA = ('2406062', 'Panki', GminaType.WIEJSKA, 'śląskie', 'kłobucki', 'powiat')
    SLASKIE_KLOBUCKI_POPOW_WIEJSKA = ('2406072', 'Popów', GminaType.WIEJSKA, 'śląskie', 'kłobucki', 'powiat')
    SLASKIE_KLOBUCKI_PRZYSTAJN_WIEJSKA = ('2406082', 'Przystajń', GminaType.WIEJSKA, 'śląskie', 'kłobucki', 'powiat')
    SLASKIE_KLOBUCKI_WRECZYCA_WIELKA_WIEJSKA = ('2406092', 'Wręczyca Wielka', GminaType.WIEJSKA, 'śląskie', 'kłobucki',
                                                'powiat')
    SLASKIE_LUBLINIECKI_LUBLINIEC_MIEJSKA = ('2407011', 'Lubliniec', GminaType.MIEJSKA, 'śląskie', 'lubliniecki',
                                             'powiat')
    SLASKIE_LUBLINIECKI_BORONOW_WIEJSKA = ('2407022', 'Boronów', GminaType.WIEJSKA, 'śląskie', 'lubliniecki', 'powiat')
    SLASKIE_LUBLINIECKI_CIASNA_WIEJSKA = ('2407032', 'Ciasna', GminaType.WIEJSKA, 'śląskie', 'lubliniecki', 'powiat')
    SLASKIE_LUBLINIECKI_HERBY_WIEJSKA = ('2407042', 'Herby', GminaType.WIEJSKA, 'śląskie', 'lubliniecki', 'powiat')
    SLASKIE_LUBLINIECKI_KOCHANOWICE_WIEJSKA = ('2407052', 'Kochanowice', GminaType.WIEJSKA, 'śląskie', 'lubliniecki',
                                               'powiat')
    SLASKIE_LUBLINIECKI_KOSZECIN_WIEJSKA = ('2407062', 'Koszęcin', GminaType.WIEJSKA, 'śląskie', 'lubliniecki',
                                            'powiat')
    SLASKIE_LUBLINIECKI_PAWONKOW_WIEJSKA = ('2407072', 'Pawonków', GminaType.WIEJSKA, 'śląskie', 'lubliniecki',
                                            'powiat')
    SLASKIE_LUBLINIECKI_WOZNIKI_MIEJSKO_WIEJSKA = ('2407083', 'Woźniki', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                   'lubliniecki', 'powiat')
    SLASKIE_MIKOLOWSKI_LAZISKA_GORNE_MIEJSKA = ('2408011', 'Łaziska Górne', GminaType.MIEJSKA, 'śląskie', 'mikołowski',
                                                'powiat')
    SLASKIE_MIKOLOWSKI_MIKOLOW_MIEJSKA = ('2408021', 'Mikołów', GminaType.MIEJSKA, 'śląskie', 'mikołowski', 'powiat')
    SLASKIE_MIKOLOWSKI_ORZESZE_MIEJSKA = ('2408031', 'Orzesze', GminaType.MIEJSKA, 'śląskie', 'mikołowski', 'powiat')
    SLASKIE_MIKOLOWSKI_ORNONTOWICE_WIEJSKA = ('2408042', 'Ornontowice', GminaType.WIEJSKA, 'śląskie', 'mikołowski',
                                              'powiat')
    SLASKIE_MIKOLOWSKI_WYRY_WIEJSKA = ('2408052', 'Wyry', GminaType.WIEJSKA, 'śląskie', 'mikołowski', 'powiat')
    SLASKIE_MYSZKOWSKI_MYSZKOW_MIEJSKA = ('2409011', 'Myszków', GminaType.MIEJSKA, 'śląskie', 'myszkowski', 'powiat')
    SLASKIE_MYSZKOWSKI_KOZIEGLOWY_MIEJSKO_WIEJSKA = ('2409023', 'Koziegłowy', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                     'myszkowski', 'powiat')
    SLASKIE_MYSZKOWSKI_NIEGOWA_WIEJSKA = ('2409032', 'Niegowa', GminaType.WIEJSKA, 'śląskie', 'myszkowski', 'powiat')
    SLASKIE_MYSZKOWSKI_PORAJ_WIEJSKA = ('2409042', 'Poraj', GminaType.WIEJSKA, 'śląskie', 'myszkowski', 'powiat')
    SLASKIE_MYSZKOWSKI_ZARKI_MIEJSKO_WIEJSKA = ('2409053', 'Żarki', GminaType.MIEJSKO_WIEJSKA, 'śląskie', 'myszkowski',
                                                'powiat')
    SLASKIE_PSZCZYNSKI_GOCZALKOWICE_ZDROJ_WIEJSKA = ('2410012', 'Goczałkowice-Zdrój', GminaType.WIEJSKA, 'śląskie',
                                                     'pszczyński', 'powiat')
    SLASKIE_PSZCZYNSKI_KOBIOR_WIEJSKA = ('2410022', 'Kobiór', GminaType.WIEJSKA, 'śląskie', 'pszczyński', 'powiat')
    SLASKIE_PSZCZYNSKI_MIEDZNA_WIEJSKA = ('2410032', 'Miedźna', GminaType.WIEJSKA, 'śląskie', 'pszczyński', 'powiat')
    SLASKIE_PSZCZYNSKI_PAWLOWICE_WIEJSKA = ('2410042', 'Pawłowice', GminaType.WIEJSKA, 'śląskie', 'pszczyński',
                                            'powiat')
    SLASKIE_PSZCZYNSKI_PSZCZYNA_MIEJSKO_WIEJSKA = ('2410053', 'Pszczyna', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                   'pszczyński', 'powiat')
    SLASKIE_PSZCZYNSKI_SUSZEC_WIEJSKA = ('2410062', 'Suszec', GminaType.WIEJSKA, 'śląskie', 'pszczyński', 'powiat')
    SLASKIE_RACIBORSKI_RACIBORZ_MIEJSKA = ('2411011', 'Racibórz', GminaType.MIEJSKA, 'śląskie', 'raciborski', 'powiat')
    SLASKIE_RACIBORSKI_KORNOWAC_WIEJSKA = ('2411022', 'Kornowac', GminaType.WIEJSKA, 'śląskie', 'raciborski', 'powiat')
    SLASKIE_RACIBORSKI_KRZANOWICE_MIEJSKO_WIEJSKA = ('2411033', 'Krzanowice', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                     'raciborski', 'powiat')
    SLASKIE_RACIBORSKI_KRZYZANOWICE_WIEJSKA = ('2411042', 'Krzyżanowice', GminaType.WIEJSKA, 'śląskie', 'raciborski',
                                               'powiat')
    SLASKIE_RACIBORSKI_KUZNIA_RACIBORSKA_MIEJSKO_WIEJSKA = ('2411053', 'Kuźnia Raciborska', GminaType.MIEJSKO_WIEJSKA,
                                                            'śląskie', 'raciborski', 'powiat')
    SLASKIE_RACIBORSKI_NEDZA_WIEJSKA = ('2411062', 'Nędza', GminaType.WIEJSKA, 'śląskie', 'raciborski', 'powiat')
    SLASKIE_RACIBORSKI_PIETROWICE_WIELKIE_WIEJSKA = ('2411072', 'Pietrowice Wielkie', GminaType.WIEJSKA, 'śląskie',
                                                     'raciborski', 'powiat')
    SLASKIE_RACIBORSKI_RUDNIK_WIEJSKA = ('2411082', 'Rudnik', GminaType.WIEJSKA, 'śląskie', 'raciborski', 'powiat')
    SLASKIE_RYBNICKI_CZERWIONKA_LESZCZYNY_MIEJSKO_WIEJSKA = ('2412013', 'Czerwionka-Leszczyny',
                                                             GminaType.MIEJSKO_WIEJSKA, 'śląskie', 'rybnicki', 'powiat')
    SLASKIE_RYBNICKI_GASZOWICE_WIEJSKA = ('2412022', 'Gaszowice', GminaType.WIEJSKA, 'śląskie', 'rybnicki', 'powiat')
    SLASKIE_RYBNICKI_JEJKOWICE_WIEJSKA = ('2412032', 'Jejkowice', GminaType.WIEJSKA, 'śląskie', 'rybnicki', 'powiat')
    SLASKIE_RYBNICKI_LYSKI_WIEJSKA = ('2412042', 'Lyski', GminaType.WIEJSKA, 'śląskie', 'rybnicki', 'powiat')
    SLASKIE_RYBNICKI_SWIERKLANY_WIEJSKA = ('2412052', 'Świerklany', GminaType.WIEJSKA, 'śląskie', 'rybnicki', 'powiat')
    SLASKIE_TARNOGORSKI_KALETY_MIEJSKA = ('2413011', 'Kalety', GminaType.MIEJSKA, 'śląskie', 'tarnogórski', 'powiat')
    SLASKIE_TARNOGORSKI_MIASTECZKO_SLASKIE_MIEJSKA = ('2413021', 'Miasteczko Śląskie', GminaType.MIEJSKA, 'śląskie',
                                                      'tarnogórski', 'powiat')
    SLASKIE_TARNOGORSKI_RADZIONKOW_MIEJSKA = ('2413031', 'Radzionków', GminaType.MIEJSKA, 'śląskie', 'tarnogórski',
                                              'powiat')
    SLASKIE_TARNOGORSKI_TARNOWSKIE_GORY_MIEJSKA = ('2413041', 'Tarnowskie Góry', GminaType.MIEJSKA, 'śląskie',
                                                   'tarnogórski', 'powiat')
    SLASKIE_TARNOGORSKI_KRUPSKI_MLYN_WIEJSKA = ('2413052', 'Krupski Młyn', GminaType.WIEJSKA, 'śląskie', 'tarnogórski',
                                                'powiat')
    SLASKIE_TARNOGORSKI_OZAROWICE_WIEJSKA = ('2413062', 'Ożarowice', GminaType.WIEJSKA, 'śląskie', 'tarnogórski',
                                             'powiat')
    SLASKIE_TARNOGORSKI_SWIERKLANIEC_WIEJSKA = ('2413072', 'Świerklaniec', GminaType.WIEJSKA, 'śląskie', 'tarnogórski',
                                                'powiat')
    SLASKIE_TARNOGORSKI_TWOROG_WIEJSKA = ('2413082', 'Tworóg', GminaType.WIEJSKA, 'śląskie', 'tarnogórski', 'powiat')
    SLASKIE_TARNOGORSKI_ZBROSLAWICE_WIEJSKA = ('2413092', 'Zbrosławice', GminaType.WIEJSKA, 'śląskie', 'tarnogórski',
                                               'powiat')
    SLASKIE_BIERUNSKO_LEDZINSKI_BIERUN_MIEJSKA = ('2414011', 'Bieruń', GminaType.MIEJSKA, 'śląskie',
                                                  'bieruńsko-lędziński', 'powiat')
    SLASKIE_BIERUNSKO_LEDZINSKI_IMIELIN_MIEJSKA = ('2414021', 'Imielin', GminaType.MIEJSKA, 'śląskie',
                                                   'bieruńsko-lędziński', 'powiat')
    SLASKIE_BIERUNSKO_LEDZINSKI_LEDZINY_MIEJSKA = ('2414031', 'Lędziny', GminaType.MIEJSKA, 'śląskie',
                                                   'bieruńsko-lędziński', 'powiat')
    SLASKIE_BIERUNSKO_LEDZINSKI_BOJSZOWY_WIEJSKA = ('2414042', 'Bojszowy', GminaType.WIEJSKA, 'śląskie',
                                                    'bieruńsko-lędziński', 'powiat')
    SLASKIE_BIERUNSKO_LEDZINSKI_CHELM_SLASKI_WIEJSKA = ('2414052', 'Chełm Śląski', GminaType.WIEJSKA, 'śląskie',
                                                        'bieruńsko-lędziński', 'powiat')
    SLASKIE_WODZISLAWSKI_PSZOW_MIEJSKA = ('2415011', 'Pszów', GminaType.MIEJSKA, 'śląskie', 'wodzisławski', 'powiat')
    SLASKIE_WODZISLAWSKI_RADLIN_MIEJSKA = ('2415021', 'Radlin', GminaType.MIEJSKA, 'śląskie', 'wodzisławski', 'powiat')
    SLASKIE_WODZISLAWSKI_RYDULTOWY_MIEJSKA = ('2415031', 'Rydułtowy', GminaType.MIEJSKA, 'śląskie', 'wodzisławski',
                                              'powiat')
    SLASKIE_WODZISLAWSKI_WODZISLAW_SLASKI_MIEJSKA = ('2415041', 'Wodzisław Śląski', GminaType.MIEJSKA, 'śląskie',
                                                     'wodzisławski', 'powiat')
    SLASKIE_WODZISLAWSKI_GODOW_WIEJSKA = ('2415052', 'Godów', GminaType.WIEJSKA, 'śląskie', 'wodzisławski', 'powiat')
    SLASKIE_WODZISLAWSKI_GORZYCE_WIEJSKA = ('2415062', 'Gorzyce', GminaType.WIEJSKA, 'śląskie', 'wodzisławski',
                                            'powiat')
    SLASKIE_WODZISLAWSKI_LUBOMIA_WIEJSKA = ('2415072', 'Lubomia', GminaType.WIEJSKA, 'śląskie', 'wodzisławski',
                                            'powiat')
    SLASKIE_WODZISLAWSKI_MARKLOWICE_WIEJSKA = ('2415082', 'Marklowice', GminaType.WIEJSKA, 'śląskie', 'wodzisławski',
                                               'powiat')
    SLASKIE_WODZISLAWSKI_MSZANA_WIEJSKA = ('2415092', 'Mszana', GminaType.WIEJSKA, 'śląskie', 'wodzisławski', 'powiat')
    SLASKIE_ZAWIERCIANSKI_POREBA_MIEJSKA = ('2416011', 'Poręba', GminaType.MIEJSKA, 'śląskie', 'zawierciański',
                                            'powiat')
    SLASKIE_ZAWIERCIANSKI_ZAWIERCIE_MIEJSKA = ('2416021', 'Zawiercie', GminaType.MIEJSKA, 'śląskie', 'zawierciański',
                                               'powiat')
    SLASKIE_ZAWIERCIANSKI_IRZADZE_WIEJSKA = ('2416032', 'Irządze', GminaType.WIEJSKA, 'śląskie', 'zawierciański',
                                             'powiat')
    SLASKIE_ZAWIERCIANSKI_KROCZYCE_WIEJSKA = ('2416042', 'Kroczyce', GminaType.WIEJSKA, 'śląskie', 'zawierciański',
                                              'powiat')
    SLASKIE_ZAWIERCIANSKI_LAZY_MIEJSKO_WIEJSKA = ('2416053', 'Łazy', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                  'zawierciański', 'powiat')
    SLASKIE_ZAWIERCIANSKI_OGRODZIENIEC_MIEJSKO_WIEJSKA = ('2416063', 'Ogrodzieniec', GminaType.MIEJSKO_WIEJSKA,
                                                          'śląskie', 'zawierciański', 'powiat')
    SLASKIE_ZAWIERCIANSKI_PILICA_MIEJSKO_WIEJSKA = ('2416073', 'Pilica', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                    'zawierciański', 'powiat')
    SLASKIE_ZAWIERCIANSKI_SZCZEKOCINY_MIEJSKO_WIEJSKA = ('2416083', 'Szczekociny', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                         'zawierciański', 'powiat')
    SLASKIE_ZAWIERCIANSKI_WLODOWICE_MIEJSKO_WIEJSKA = ('2416093', 'Włodowice', GminaType.MIEJSKO_WIEJSKA, 'śląskie',
                                                       'zawierciański', 'powiat')
    SLASKIE_ZAWIERCIANSKI_ZARNOWIEC_WIEJSKA = ('2416102', 'Żarnowiec', GminaType.WIEJSKA, 'śląskie', 'zawierciański',
                                               'powiat')
    SLASKIE_ZYWIECKI_ZYWIEC_MIEJSKA = ('2417011', 'Żywiec', GminaType.MIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_CZERNICHOW_WIEJSKA = ('2417022', 'Czernichów', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_GILOWICE_WIEJSKA = ('2417032', 'Gilowice', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_JELESNIA_WIEJSKA = ('2417042', 'Jeleśnia', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_KOSZARAWA_WIEJSKA = ('2417052', 'Koszarawa', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_LIPOWA_WIEJSKA = ('2417062', 'Lipowa', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_LEKAWICA_WIEJSKA = ('2417072', 'Łękawica', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_LODYGOWICE_WIEJSKA = ('2417082', 'Łodygowice', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_MILOWKA_WIEJSKA = ('2417092', 'Milówka', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_RADZIECHOWY_WIEPRZ_WIEJSKA = ('2417102', 'Radziechowy-Wieprz', GminaType.WIEJSKA, 'śląskie',
                                                   'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_RAJCZA_WIEJSKA = ('2417112', 'Rajcza', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_SLEMIEN_WIEJSKA = ('2417122', 'Ślemień', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_SWINNA_WIEJSKA = ('2417132', 'Świnna', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_UJSOLY_WIEJSKA = ('2417142', 'Ujsoły', GminaType.WIEJSKA, 'śląskie', 'żywiecki', 'powiat')
    SLASKIE_ZYWIECKI_WEGIERSKA_GORKA_WIEJSKA = ('2417152', 'Węgierska Górka', GminaType.WIEJSKA, 'śląskie', 'żywiecki',
                                                'powiat')
    SLASKIE_BIELSKO_BIALA_BIELSKO_BIALA_MIEJSKA = ('2461011', 'Bielsko-Biała', GminaType.MIEJSKA, 'śląskie',
                                                   'Bielsko-Biała', 'miasto na prawach powiatu')
    SLASKIE_BYTOM_BYTOM_MIEJSKA = ('2462011', 'Bytom', GminaType.MIEJSKA, 'śląskie', 'Bytom',
                                   'miasto na prawach powiatu')
    SLASKIE_CHORZOW_CHORZOW_MIEJSKA = ('2463011', 'Chorzów', GminaType.MIEJSKA, 'śląskie', 'Chorzów',
                                       'miasto na prawach powiatu')
    SLASKIE_CZESTOCHOWA_CZESTOCHOWA_MIEJSKA = ('2464011', 'Częstochowa', GminaType.MIEJSKA, 'śląskie', 'Częstochowa',
                                               'miasto na prawach powiatu')
    SLASKIE_DABROWA_GORNICZA_DABROWA_GORNICZA_MIEJSKA = ('2465011', 'Dąbrowa Górnicza', GminaType.MIEJSKA, 'śląskie',
                                                         'Dąbrowa Górnicza', 'miasto na prawach powiatu')
    SLASKIE_GLIWICE_GLIWICE_MIEJSKA = ('2466011', 'Gliwice', GminaType.MIEJSKA, 'śląskie', 'Gliwice',
                                       'miasto na prawach powiatu')
    SLASKIE_JASTRZEBIE_ZDROJ_JASTRZEBIE_ZDROJ_MIEJSKA = ('2467011', 'Jastrzębie-Zdrój', GminaType.MIEJSKA, 'śląskie',
                                                         'Jastrzębie-Zdrój', 'miasto na prawach powiatu')
    SLASKIE_JAWORZNO_JAWORZNO_MIEJSKA = ('2468011', 'Jaworzno', GminaType.MIEJSKA, 'śląskie', 'Jaworzno',
                                         'miasto na prawach powiatu')
    SLASKIE_KATOWICE_KATOWICE_MIEJSKA = ('2469011', 'Katowice', GminaType.MIEJSKA, 'śląskie', 'Katowice',
                                         'miasto na prawach powiatu')
    SLASKIE_MYSLOWICE_MYSLOWICE_MIEJSKA = ('2470011', 'Mysłowice', GminaType.MIEJSKA, 'śląskie', 'Mysłowice',
                                           'miasto na prawach powiatu')
    SLASKIE_PIEKARY_SLASKIE_PIEKARY_SLASKIE_MIEJSKA = ('2471011', 'Piekary Śląskie', GminaType.MIEJSKA, 'śląskie',
                                                       'Piekary Śląskie', 'miasto na prawach powiatu')
    SLASKIE_RUDA_SLASKA_RUDA_SLASKA_MIEJSKA = ('2472011', 'Ruda Śląska', GminaType.MIEJSKA, 'śląskie', 'Ruda Śląska',
                                               'miasto na prawach powiatu')
    SLASKIE_RYBNIK_RYBNIK_MIEJSKA = ('2473011', 'Rybnik', GminaType.MIEJSKA, 'śląskie', 'Rybnik',
                                     'miasto na prawach powiatu')
    SLASKIE_SIEMIANOWICE_SLASKIE_SIEMIANOWICE_SLASKIE_MIEJSKA = ('2474011', 'Siemianowice Śląskie', GminaType.MIEJSKA,
                                                                 'śląskie', 'Siemianowice Śląskie',
                                                                 'miasto na prawach powiatu')
    SLASKIE_SOSNOWIEC_SOSNOWIEC_MIEJSKA = ('2475011', 'Sosnowiec', GminaType.MIEJSKA, 'śląskie', 'Sosnowiec',
                                           'miasto na prawach powiatu')
    SLASKIE_SWIETOCHLOWICE_SWIETOCHLOWICE_MIEJSKA = ('2476011', 'Świętochłowice', GminaType.MIEJSKA, 'śląskie',
                                                     'Świętochłowice', 'miasto na prawach powiatu')
    SLASKIE_TYCHY_TYCHY_MIEJSKA = ('2477011', 'Tychy', GminaType.MIEJSKA, 'śląskie', 'Tychy',
                                   'miasto na prawach powiatu')
    SLASKIE_ZABRZE_ZABRZE_MIEJSKA = ('2478011', 'Zabrze', GminaType.MIEJSKA, 'śląskie', 'Zabrze',
                                     'miasto na prawach powiatu')
    SLASKIE_ZORY_ZORY_MIEJSKA = ('2479011', 'Żory', GminaType.MIEJSKA, 'śląskie', 'Żory', 'miasto na prawach powiatu')

    # Świętokrzyskie
    SWIETOKRZYSKIE_BUSKI_BUSKO_ZDROJ_MIEJSKO_WIEJSKA = ('2601013', 'Busko-Zdrój', GminaType.MIEJSKO_WIEJSKA,
                                                        'świętokrzyskie', 'buski', 'powiat')
    SWIETOKRZYSKIE_BUSKI_GNOJNO_WIEJSKA = ('2601022', 'Gnojno', GminaType.WIEJSKA, 'świętokrzyskie', 'buski', 'powiat')
    SWIETOKRZYSKIE_BUSKI_NOWY_KORCZYN_MIEJSKO_WIEJSKA = ('2601033', 'Nowy Korczyn', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'buski', 'powiat')
    SWIETOKRZYSKIE_BUSKI_PACANOW_MIEJSKO_WIEJSKA = ('2601043', 'Pacanów', GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                    'buski', 'powiat')
    SWIETOKRZYSKIE_BUSKI_SOLEC_ZDROJ_WIEJSKA = ('2601052', 'Solec-Zdrój', GminaType.WIEJSKA, 'świętokrzyskie', 'buski',
                                                'powiat')
    SWIETOKRZYSKIE_BUSKI_STOPNICA_MIEJSKO_WIEJSKA = ('2601063', 'Stopnica', GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                     'buski', 'powiat')
    SWIETOKRZYSKIE_BUSKI_TUCZEPY_WIEJSKA = ('2601072', 'Tuczępy', GminaType.WIEJSKA, 'świętokrzyskie', 'buski',
                                            'powiat')
    SWIETOKRZYSKIE_BUSKI_WISLICA_MIEJSKO_WIEJSKA = ('2601083', 'Wiślica', GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                    'buski', 'powiat')
    SWIETOKRZYSKIE_JEDRZEJOWSKI_IMIELNO_WIEJSKA = ('2602012', 'Imielno', GminaType.WIEJSKA, 'świętokrzyskie',
                                                   'jędrzejowski', 'powiat')
    SWIETOKRZYSKIE_JEDRZEJOWSKI_JEDRZEJOW_MIEJSKO_WIEJSKA = ('2602023', 'Jędrzejów', GminaType.MIEJSKO_WIEJSKA,
                                                             'świętokrzyskie', 'jędrzejowski', 'powiat')
    SWIETOKRZYSKIE_JEDRZEJOWSKI_MALOGOSZCZ_MIEJSKO_WIEJSKA = ('2602033', 'Małogoszcz', GminaType.MIEJSKO_WIEJSKA,
                                                              'świętokrzyskie', 'jędrzejowski', 'powiat')
    SWIETOKRZYSKIE_JEDRZEJOWSKI_NAGLOWICE_WIEJSKA = ('2602042', 'Nagłowice', GminaType.WIEJSKA, 'świętokrzyskie',
                                                     'jędrzejowski', 'powiat')
    SWIETOKRZYSKIE_JEDRZEJOWSKI_OKSA_WIEJSKA = ('2602052', 'Oksa', GminaType.WIEJSKA, 'świętokrzyskie', 'jędrzejowski',
                                                'powiat')
    SWIETOKRZYSKIE_JEDRZEJOWSKI_SEDZISZOW_MIEJSKO_WIEJSKA = ('2602063', 'Sędziszów', GminaType.MIEJSKO_WIEJSKA,
                                                             'świętokrzyskie', 'jędrzejowski', 'powiat')
    SWIETOKRZYSKIE_JEDRZEJOWSKI_SLUPIA_WIEJSKA = ('2602072', 'Słupia', GminaType.WIEJSKA, 'świętokrzyskie',
                                                  'jędrzejowski', 'powiat')
    SWIETOKRZYSKIE_JEDRZEJOWSKI_SOBKOW_MIEJSKO_WIEJSKA = ('2602083', 'Sobków', GminaType.MIEJSKO_WIEJSKA,
                                                          'świętokrzyskie', 'jędrzejowski', 'powiat')
    SWIETOKRZYSKIE_JEDRZEJOWSKI_WODZISLAW_MIEJSKO_WIEJSKA = ('2602093', 'Wodzisław', GminaType.MIEJSKO_WIEJSKA,
                                                             'świętokrzyskie', 'jędrzejowski', 'powiat')
    SWIETOKRZYSKIE_KAZIMIERSKI_BEJSCE_WIEJSKA = ('2603012', 'Bejsce', GminaType.WIEJSKA, 'świętokrzyskie',
                                                 'kazimierski', 'powiat')
    SWIETOKRZYSKIE_KAZIMIERSKI_CZARNOCIN_WIEJSKA = ('2603022', 'Czarnocin', GminaType.WIEJSKA, 'świętokrzyskie',
                                                    'kazimierski', 'powiat')
    SWIETOKRZYSKIE_KAZIMIERSKI_KAZIMIERZA_WIELKA_MIEJSKO_WIEJSKA = ('2603033', 'Kazimierza Wielka',
                                                                    GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                                    'kazimierski', 'powiat')
    SWIETOKRZYSKIE_KAZIMIERSKI_OPATOWIEC_MIEJSKO_WIEJSKA = ('2603043', 'Opatowiec', GminaType.MIEJSKO_WIEJSKA,
                                                            'świętokrzyskie', 'kazimierski', 'powiat')
    SWIETOKRZYSKIE_KAZIMIERSKI_SKALBMIERZ_MIEJSKO_WIEJSKA = ('2603053', 'Skalbmierz', GminaType.MIEJSKO_WIEJSKA,
                                                             'świętokrzyskie', 'kazimierski', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_BIELINY_WIEJSKA = ('2604012', 'Bieliny', GminaType.WIEJSKA, 'świętokrzyskie', 'kielecki',
                                               'powiat')
    SWIETOKRZYSKIE_KIELECKI_BODZENTYN_MIEJSKO_WIEJSKA = ('2604023', 'Bodzentyn', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_CHECINY_MIEJSKO_WIEJSKA = ('2604033', 'Chęciny', GminaType.MIEJSKO_WIEJSKA,
                                                       'świętokrzyskie', 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_CHMIELNIK_MIEJSKO_WIEJSKA = ('2604043', 'Chmielnik', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_DALESZYCE_MIEJSKO_WIEJSKA = ('2604053', 'Daleszyce', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_GORNO_WIEJSKA = ('2604062', 'Górno', GminaType.WIEJSKA, 'świętokrzyskie', 'kielecki',
                                             'powiat')
    SWIETOKRZYSKIE_KIELECKI_LAGOW_MIEJSKO_WIEJSKA = ('2604073', 'Łagów', GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                     'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_LOPUSZNO_MIEJSKO_WIEJSKA = ('2604083', 'Łopuszno', GminaType.MIEJSKO_WIEJSKA,
                                                        'świętokrzyskie', 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_MASLOW_WIEJSKA = ('2604092', 'Masłów', GminaType.WIEJSKA, 'świętokrzyskie', 'kielecki',
                                              'powiat')
    SWIETOKRZYSKIE_KIELECKI_MIEDZIANA_GORA_WIEJSKA = ('2604102', 'Miedziana Góra', GminaType.WIEJSKA, 'świętokrzyskie',
                                                      'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_MNIOW_WIEJSKA = ('2604112', 'Mniów', GminaType.WIEJSKA, 'świętokrzyskie', 'kielecki',
                                             'powiat')
    SWIETOKRZYSKIE_KIELECKI_MORAWICA_MIEJSKO_WIEJSKA = ('2604123', 'Morawica', GminaType.MIEJSKO_WIEJSKA,
                                                        'świętokrzyskie', 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_NOWA_SLUPIA_MIEJSKO_WIEJSKA = ('2604133', 'Nowa Słupia', GminaType.MIEJSKO_WIEJSKA,
                                                           'świętokrzyskie', 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_PIEKOSZOW_MIEJSKO_WIEJSKA = ('2604143', 'Piekoszów', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_PIERZCHNICA_MIEJSKO_WIEJSKA = ('2604153', 'Pierzchnica', GminaType.MIEJSKO_WIEJSKA,
                                                           'świętokrzyskie', 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_RAKOW_WIEJSKA = ('2604162', 'Raków', GminaType.WIEJSKA, 'świętokrzyskie', 'kielecki',
                                             'powiat')
    SWIETOKRZYSKIE_KIELECKI_NOWINY_WIEJSKA = ('2604172', 'Nowiny', GminaType.WIEJSKA, 'świętokrzyskie', 'kielecki',
                                              'powiat')
    SWIETOKRZYSKIE_KIELECKI_STRAWCZYN_WIEJSKA = ('2604182', 'Strawczyn', GminaType.WIEJSKA, 'świętokrzyskie',
                                                 'kielecki', 'powiat')
    SWIETOKRZYSKIE_KIELECKI_ZAGNANSK_WIEJSKA = ('2604192', 'Zagnańsk', GminaType.WIEJSKA, 'świętokrzyskie', 'kielecki',
                                                'powiat')
    SWIETOKRZYSKIE_KONECKI_FALKOW_WIEJSKA = ('2605012', 'Fałków', GminaType.WIEJSKA, 'świętokrzyskie', 'konecki',
                                             'powiat')
    SWIETOKRZYSKIE_KONECKI_GOWARCZOW_MIEJSKO_WIEJSKA = ('2605023', 'Gowarczów', GminaType.MIEJSKO_WIEJSKA,
                                                        'świętokrzyskie', 'konecki', 'powiat')
    SWIETOKRZYSKIE_KONECKI_KONSKIE_MIEJSKO_WIEJSKA = ('2605033', 'Końskie', GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                      'konecki', 'powiat')
    SWIETOKRZYSKIE_KONECKI_RADOSZYCE_MIEJSKO_WIEJSKA = ('2605043', 'Radoszyce', GminaType.MIEJSKO_WIEJSKA,
                                                        'świętokrzyskie', 'konecki', 'powiat')
    SWIETOKRZYSKIE_KONECKI_RUDA_MALENIECKA_WIEJSKA = ('2605052', 'Ruda Maleniecka', GminaType.WIEJSKA, 'świętokrzyskie',
                                                      'konecki', 'powiat')
    SWIETOKRZYSKIE_KONECKI_SLUPIA_KONECKA_WIEJSKA = ('2605062', 'Słupia Konecka', GminaType.WIEJSKA, 'świętokrzyskie',
                                                     'konecki', 'powiat')
    SWIETOKRZYSKIE_KONECKI_SMYKOW_WIEJSKA = ('2605072', 'Smyków', GminaType.WIEJSKA, 'świętokrzyskie', 'konecki',
                                             'powiat')
    SWIETOKRZYSKIE_KONECKI_STAPORKOW_MIEJSKO_WIEJSKA = ('2605083', 'Stąporków', GminaType.MIEJSKO_WIEJSKA,
                                                        'świętokrzyskie', 'konecki', 'powiat')
    SWIETOKRZYSKIE_OPATOWSKI_BACKOWICE_WIEJSKA = ('2606012', 'Baćkowice', GminaType.WIEJSKA, 'świętokrzyskie',
                                                  'opatowski', 'powiat')
    SWIETOKRZYSKIE_OPATOWSKI_IWANISKA_MIEJSKO_WIEJSKA = ('2606023', 'Iwaniska', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'opatowski', 'powiat')
    SWIETOKRZYSKIE_OPATOWSKI_LIPNIK_WIEJSKA = ('2606032', 'Lipnik', GminaType.WIEJSKA, 'świętokrzyskie', 'opatowski',
                                               'powiat')
    SWIETOKRZYSKIE_OPATOWSKI_OPATOW_MIEJSKO_WIEJSKA = ('2606043', 'Opatów', GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                       'opatowski', 'powiat')
    SWIETOKRZYSKIE_OPATOWSKI_OZAROW_MIEJSKO_WIEJSKA = ('2606053', 'Ożarów', GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                       'opatowski', 'powiat')
    SWIETOKRZYSKIE_OPATOWSKI_SADOWIE_WIEJSKA = ('2606062', 'Sadowie', GminaType.WIEJSKA, 'świętokrzyskie', 'opatowski',
                                                'powiat')
    SWIETOKRZYSKIE_OPATOWSKI_TARLOW_WIEJSKA = ('2606072', 'Tarłów', GminaType.WIEJSKA, 'świętokrzyskie', 'opatowski',
                                               'powiat')
    SWIETOKRZYSKIE_OPATOWSKI_WOJCIECHOWICE_WIEJSKA = ('2606082', 'Wojciechowice', GminaType.WIEJSKA, 'świętokrzyskie',
                                                      'opatowski', 'powiat')
    SWIETOKRZYSKIE_OSTROWIECKI_OSTROWIEC_SWIETOKRZYSKI_MIEJSKA = ('2607011', 'Ostrowiec Świętokrzyski',
                                                                  GminaType.MIEJSKA, 'świętokrzyskie', 'ostrowiecki',
                                                                  'powiat')
    SWIETOKRZYSKIE_OSTROWIECKI_BALTOW_WIEJSKA = ('2607022', 'Bałtów', GminaType.WIEJSKA, 'świętokrzyskie',
                                                 'ostrowiecki', 'powiat')
    SWIETOKRZYSKIE_OSTROWIECKI_BODZECHOW_WIEJSKA = ('2607032', 'Bodzechów', GminaType.WIEJSKA, 'świętokrzyskie',
                                                    'ostrowiecki', 'powiat')
    SWIETOKRZYSKIE_OSTROWIECKI_CMIELOW_MIEJSKO_WIEJSKA = ('2607043', 'Ćmielów', GminaType.MIEJSKO_WIEJSKA,
                                                          'świętokrzyskie', 'ostrowiecki', 'powiat')
    SWIETOKRZYSKIE_OSTROWIECKI_KUNOW_MIEJSKO_WIEJSKA = ('2607053', 'Kunów', GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                        'ostrowiecki', 'powiat')
    SWIETOKRZYSKIE_OSTROWIECKI_WASNIOW_WIEJSKA = ('2607062', 'Waśniów', GminaType.WIEJSKA, 'świętokrzyskie',
                                                  'ostrowiecki', 'powiat')
    SWIETOKRZYSKIE_PINCZOWSKI_DZIALOSZYCE_MIEJSKO_WIEJSKA = ('2608013', 'Działoszyce', GminaType.MIEJSKO_WIEJSKA,
                                                             'świętokrzyskie', 'pińczowski', 'powiat')
    SWIETOKRZYSKIE_PINCZOWSKI_KIJE_WIEJSKA = ('2608022', 'Kije', GminaType.WIEJSKA, 'świętokrzyskie', 'pińczowski',
                                              'powiat')
    SWIETOKRZYSKIE_PINCZOWSKI_MICHALOW_WIEJSKA = ('2608032', 'Michałów', GminaType.WIEJSKA, 'świętokrzyskie',
                                                  'pińczowski', 'powiat')
    SWIETOKRZYSKIE_PINCZOWSKI_PINCZOW_MIEJSKO_WIEJSKA = ('2608043', 'Pińczów', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'pińczowski', 'powiat')
    SWIETOKRZYSKIE_PINCZOWSKI_ZLOTA_WIEJSKA = ('2608052', 'Złota', GminaType.WIEJSKA, 'świętokrzyskie', 'pińczowski',
                                               'powiat')
    SWIETOKRZYSKIE_SANDOMIERSKI_SANDOMIERZ_MIEJSKA = ('2609011', 'Sandomierz', GminaType.MIEJSKA, 'świętokrzyskie',
                                                      'sandomierski', 'powiat')
    SWIETOKRZYSKIE_SANDOMIERSKI_DWIKOZY_WIEJSKA = ('2609022', 'Dwikozy', GminaType.WIEJSKA, 'świętokrzyskie',
                                                   'sandomierski', 'powiat')
    SWIETOKRZYSKIE_SANDOMIERSKI_KLIMONTOW_MIEJSKO_WIEJSKA = ('2609033', 'Klimontów', GminaType.MIEJSKO_WIEJSKA,
                                                             'świętokrzyskie', 'sandomierski', 'powiat')
    SWIETOKRZYSKIE_SANDOMIERSKI_KOPRZYWNICA_MIEJSKO_WIEJSKA = ('2609043', 'Koprzywnica', GminaType.MIEJSKO_WIEJSKA,
                                                               'świętokrzyskie', 'sandomierski', 'powiat')
    SWIETOKRZYSKIE_SANDOMIERSKI_LONIOW_WIEJSKA = ('2609052', 'Łoniów', GminaType.WIEJSKA, 'świętokrzyskie',
                                                  'sandomierski', 'powiat')
    SWIETOKRZYSKIE_SANDOMIERSKI_OBRAZOW_WIEJSKA = ('2609062', 'Obrazów', GminaType.WIEJSKA, 'świętokrzyskie',
                                                   'sandomierski', 'powiat')
    SWIETOKRZYSKIE_SANDOMIERSKI_SAMBORZEC_WIEJSKA = ('2609072', 'Samborzec', GminaType.WIEJSKA, 'świętokrzyskie',
                                                     'sandomierski', 'powiat')
    SWIETOKRZYSKIE_SANDOMIERSKI_WILCZYCE_WIEJSKA = ('2609082', 'Wilczyce', GminaType.WIEJSKA, 'świętokrzyskie',
                                                    'sandomierski', 'powiat')
    SWIETOKRZYSKIE_SANDOMIERSKI_ZAWICHOST_MIEJSKO_WIEJSKA = ('2609093', 'Zawichost', GminaType.MIEJSKO_WIEJSKA,
                                                             'świętokrzyskie', 'sandomierski', 'powiat')
    SWIETOKRZYSKIE_SKARZYSKI_SKARZYSKO_KAMIENNA_MIEJSKA = ('2610011', 'Skarżysko-Kamienna', GminaType.MIEJSKA,
                                                           'świętokrzyskie', 'skarżyski', 'powiat')
    SWIETOKRZYSKIE_SKARZYSKI_BLIZYN_WIEJSKA = ('2610022', 'Bliżyn', GminaType.WIEJSKA, 'świętokrzyskie', 'skarżyski',
                                               'powiat')
    SWIETOKRZYSKIE_SKARZYSKI_LACZNA_WIEJSKA = ('2610032', 'Łączna', GminaType.WIEJSKA, 'świętokrzyskie', 'skarżyski',
                                               'powiat')
    SWIETOKRZYSKIE_SKARZYSKI_SKARZYSKO_KOSCIELNE_WIEJSKA = ('2610042', 'Skarżysko Kościelne', GminaType.WIEJSKA,
                                                            'świętokrzyskie', 'skarżyski', 'powiat')
    SWIETOKRZYSKIE_SKARZYSKI_SUCHEDNIOW_MIEJSKO_WIEJSKA = ('2610053', 'Suchedniów', GminaType.MIEJSKO_WIEJSKA,
                                                           'świętokrzyskie', 'skarżyski', 'powiat')
    SWIETOKRZYSKIE_STARACHOWICKI_STARACHOWICE_MIEJSKA = ('2611011', 'Starachowice', GminaType.MIEJSKA, 'świętokrzyskie',
                                                         'starachowicki', 'powiat')
    SWIETOKRZYSKIE_STARACHOWICKI_BRODY_WIEJSKA = ('2611022', 'Brody', GminaType.WIEJSKA, 'świętokrzyskie',
                                                  'starachowicki', 'powiat')
    SWIETOKRZYSKIE_STARACHOWICKI_MIRZEC_WIEJSKA = ('2611032', 'Mirzec', GminaType.WIEJSKA, 'świętokrzyskie',
                                                   'starachowicki', 'powiat')
    SWIETOKRZYSKIE_STARACHOWICKI_PAWLOW_WIEJSKA = ('2611042', 'Pawłów', GminaType.WIEJSKA, 'świętokrzyskie',
                                                   'starachowicki', 'powiat')
    SWIETOKRZYSKIE_STARACHOWICKI_WACHOCK_MIEJSKO_WIEJSKA = ('2611053', 'Wąchock', GminaType.MIEJSKO_WIEJSKA,
                                                            'świętokrzyskie', 'starachowicki', 'powiat')
    SWIETOKRZYSKIE_STASZOWSKI_BOGORIA_MIEJSKO_WIEJSKA = ('2612013', 'Bogoria', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'staszowski', 'powiat')
    SWIETOKRZYSKIE_STASZOWSKI_LUBNICE_WIEJSKA = ('2612022', 'Łubnice', GminaType.WIEJSKA, 'świętokrzyskie',
                                                 'staszowski', 'powiat')
    SWIETOKRZYSKIE_STASZOWSKI_OLESNICA_MIEJSKO_WIEJSKA = ('2612033', 'Oleśnica', GminaType.MIEJSKO_WIEJSKA,
                                                          'świętokrzyskie', 'staszowski', 'powiat')
    SWIETOKRZYSKIE_STASZOWSKI_OSIEK_MIEJSKO_WIEJSKA = ('2612043', 'Osiek', GminaType.MIEJSKO_WIEJSKA, 'świętokrzyskie',
                                                       'staszowski', 'powiat')
    SWIETOKRZYSKIE_STASZOWSKI_POLANIEC_MIEJSKO_WIEJSKA = ('2612053', 'Połaniec', GminaType.MIEJSKO_WIEJSKA,
                                                          'świętokrzyskie', 'staszowski', 'powiat')
    SWIETOKRZYSKIE_STASZOWSKI_RYTWIANY_WIEJSKA = ('2612062', 'Rytwiany', GminaType.WIEJSKA, 'świętokrzyskie',
                                                  'staszowski', 'powiat')
    SWIETOKRZYSKIE_STASZOWSKI_STASZOW_MIEJSKO_WIEJSKA = ('2612073', 'Staszów', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'staszowski', 'powiat')
    SWIETOKRZYSKIE_STASZOWSKI_SZYDLOW_MIEJSKO_WIEJSKA = ('2612083', 'Szydłów', GminaType.MIEJSKO_WIEJSKA,
                                                         'świętokrzyskie', 'staszowski', 'powiat')
    SWIETOKRZYSKIE_WLOSZCZOWSKI_KLUCZEWSKO_WIEJSKA = ('2613012', 'Kluczewsko', GminaType.WIEJSKA, 'świętokrzyskie',
                                                      'włoszczowski', 'powiat')
    SWIETOKRZYSKIE_WLOSZCZOWSKI_KRASOCIN_WIEJSKA = ('2613022', 'Krasocin', GminaType.WIEJSKA, 'świętokrzyskie',
                                                    'włoszczowski', 'powiat')
    SWIETOKRZYSKIE_WLOSZCZOWSKI_MOSKORZEW_WIEJSKA = ('2613032', 'Moskorzew', GminaType.WIEJSKA, 'świętokrzyskie',
                                                     'włoszczowski', 'powiat')
    SWIETOKRZYSKIE_WLOSZCZOWSKI_RADKOW_WIEJSKA = ('2613042', 'Radków', GminaType.WIEJSKA, 'świętokrzyskie',
                                                  'włoszczowski', 'powiat')
    SWIETOKRZYSKIE_WLOSZCZOWSKI_SECEMIN_WIEJSKA = ('2613052', 'Secemin', GminaType.WIEJSKA, 'świętokrzyskie',
                                                   'włoszczowski', 'powiat')
    SWIETOKRZYSKIE_WLOSZCZOWSKI_WLOSZCZOWA_MIEJSKO_WIEJSKA = ('2613063', 'Włoszczowa', GminaType.MIEJSKO_WIEJSKA,
                                                              'świętokrzyskie', 'włoszczowski', 'powiat')
    SWIETOKRZYSKIE_KIELCE_KIELCE_MIEJSKA = ('2661011', 'Kielce', GminaType.MIEJSKA, 'świętokrzyskie', 'Kielce',
                                            'miasto na prawach powiatu')

    # Warmińsko-mazurskie
    WARMINSKO_MAZURSKIE_BARTOSZYCKI_BARTOSZYCE_MIEJSKA = ('2801011', 'Bartoszyce', GminaType.MIEJSKA,
                                                          'warmińsko-mazurskie', 'bartoszycki', 'powiat')
    WARMINSKO_MAZURSKIE_BARTOSZYCKI_GOROWO_ILAWECKIE_MIEJSKA = ('2801021', 'Górowo Iławeckie', GminaType.MIEJSKA,
                                                                'warmińsko-mazurskie', 'bartoszycki', 'powiat')
    WARMINSKO_MAZURSKIE_BARTOSZYCKI_BARTOSZYCE_WIEJSKA = ('2801032', 'Bartoszyce', GminaType.WIEJSKA,
                                                          'warmińsko-mazurskie', 'bartoszycki', 'powiat')
    WARMINSKO_MAZURSKIE_BARTOSZYCKI_BISZTYNEK_MIEJSKO_WIEJSKA = ('2801043', 'Bisztynek', GminaType.MIEJSKO_WIEJSKA,
                                                                 'warmińsko-mazurskie', 'bartoszycki', 'powiat')
    WARMINSKO_MAZURSKIE_BARTOSZYCKI_GOROWO_ILAWECKIE_WIEJSKA = ('2801052', 'Górowo Iławeckie', GminaType.WIEJSKA,
                                                                'warmińsko-mazurskie', 'bartoszycki', 'powiat')
    WARMINSKO_MAZURSKIE_BARTOSZYCKI_SEPOPOL_MIEJSKO_WIEJSKA = ('2801063', 'Sępopol', GminaType.MIEJSKO_WIEJSKA,
                                                               'warmińsko-mazurskie', 'bartoszycki', 'powiat')
    WARMINSKO_MAZURSKIE_BRANIEWSKI_BRANIEWO_MIEJSKA = ('2802011', 'Braniewo', GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                       'braniewski', 'powiat')
    WARMINSKO_MAZURSKIE_BRANIEWSKI_BRANIEWO_WIEJSKA = ('2802022', 'Braniewo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                       'braniewski', 'powiat')
    WARMINSKO_MAZURSKIE_BRANIEWSKI_FROMBORK_MIEJSKO_WIEJSKA = ('2802033', 'Frombork', GminaType.MIEJSKO_WIEJSKA,
                                                               'warmińsko-mazurskie', 'braniewski', 'powiat')
    WARMINSKO_MAZURSKIE_BRANIEWSKI_LELKOWO_WIEJSKA = ('2802042', 'Lelkowo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                      'braniewski', 'powiat')
    WARMINSKO_MAZURSKIE_BRANIEWSKI_PIENIEZNO_MIEJSKO_WIEJSKA = ('2802053', 'Pieniężno', GminaType.MIEJSKO_WIEJSKA,
                                                                'warmińsko-mazurskie', 'braniewski', 'powiat')
    WARMINSKO_MAZURSKIE_BRANIEWSKI_PLOSKINIA_WIEJSKA = ('2802062', 'Płoskinia', GminaType.WIEJSKA,
                                                        'warmińsko-mazurskie', 'braniewski', 'powiat')
    WARMINSKO_MAZURSKIE_BRANIEWSKI_WILCZETA_WIEJSKA = ('2802072', 'Wilczęta', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                       'braniewski', 'powiat')
    WARMINSKO_MAZURSKIE_DZIALDOWSKI_DZIALDOWO_MIEJSKA = ('2803011', 'Działdowo', GminaType.MIEJSKA,
                                                         'warmińsko-mazurskie', 'działdowski', 'powiat')
    WARMINSKO_MAZURSKIE_DZIALDOWSKI_DZIALDOWO_WIEJSKA = ('2803022', 'Działdowo', GminaType.WIEJSKA,
                                                         'warmińsko-mazurskie', 'działdowski', 'powiat')
    WARMINSKO_MAZURSKIE_DZIALDOWSKI_ILOWO_OSADA_WIEJSKA = ('2803032', 'Iłowo-Osada', GminaType.WIEJSKA,
                                                           'warmińsko-mazurskie', 'działdowski', 'powiat')
    WARMINSKO_MAZURSKIE_DZIALDOWSKI_LIDZBARK_MIEJSKO_WIEJSKA = ('2803043', 'Lidzbark', GminaType.MIEJSKO_WIEJSKA,
                                                                'warmińsko-mazurskie', 'działdowski', 'powiat')
    WARMINSKO_MAZURSKIE_DZIALDOWSKI_PLOSNICA_WIEJSKA = ('2803052', 'Płośnica', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                        'działdowski', 'powiat')
    WARMINSKO_MAZURSKIE_DZIALDOWSKI_RYBNO_WIEJSKA = ('2803062', 'Rybno', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'działdowski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLASKI_ELBLAG_WIEJSKA = ('2804012', 'Elbląg', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                   'elbląski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLASKI_GODKOWO_WIEJSKA = ('2804022', 'Godkowo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                    'elbląski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLASKI_GRONOWO_ELBLASKIE_WIEJSKA = ('2804032', 'Gronowo Elbląskie', GminaType.WIEJSKA,
                                                              'warmińsko-mazurskie', 'elbląski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLASKI_MARKUSY_WIEJSKA = ('2804042', 'Markusy', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                    'elbląski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLASKI_MILEJEWO_WIEJSKA = ('2804052', 'Milejewo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'elbląski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLASKI_MLYNARY_MIEJSKO_WIEJSKA = ('2804063', 'Młynary', GminaType.MIEJSKO_WIEJSKA,
                                                            'warmińsko-mazurskie', 'elbląski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLASKI_PASLEK_MIEJSKO_WIEJSKA = ('2804073', 'Pasłęk', GminaType.MIEJSKO_WIEJSKA,
                                                           'warmińsko-mazurskie', 'elbląski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLASKI_RYCHLIKI_WIEJSKA = ('2804082', 'Rychliki', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'elbląski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLASKI_TOLKMICKO_MIEJSKO_WIEJSKA = ('2804093', 'Tolkmicko', GminaType.MIEJSKO_WIEJSKA,
                                                              'warmińsko-mazurskie', 'elbląski', 'powiat')
    WARMINSKO_MAZURSKIE_ELCKI_ELK_MIEJSKA = ('2805011', 'Ełk', GminaType.MIEJSKA, 'warmińsko-mazurskie', 'ełcki',
                                             'powiat')
    WARMINSKO_MAZURSKIE_ELCKI_ELK_WIEJSKA = ('2805022', 'Ełk', GminaType.WIEJSKA, 'warmińsko-mazurskie', 'ełcki',
                                             'powiat')
    WARMINSKO_MAZURSKIE_ELCKI_KALINOWO_WIEJSKA = ('2805032', 'Kalinowo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                  'ełcki', 'powiat')
    WARMINSKO_MAZURSKIE_ELCKI_PROSTKI_WIEJSKA = ('2805042', 'Prostki', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                 'ełcki', 'powiat')
    WARMINSKO_MAZURSKIE_ELCKI_STARE_JUCHY_WIEJSKA = ('2805052', 'Stare Juchy', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'ełcki', 'powiat')
    WARMINSKO_MAZURSKIE_GIZYCKI_GIZYCKO_MIEJSKA = ('2806011', 'Giżycko', GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                   'giżycki', 'powiat')
    WARMINSKO_MAZURSKIE_GIZYCKI_GIZYCKO_WIEJSKA = ('2806042', 'Giżycko', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                   'giżycki', 'powiat')
    WARMINSKO_MAZURSKIE_GIZYCKI_KRUKLANKI_WIEJSKA = ('2806052', 'Kruklanki', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'giżycki', 'powiat')
    WARMINSKO_MAZURSKIE_GIZYCKI_MILKI_WIEJSKA = ('2806062', 'Miłki', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                 'giżycki', 'powiat')
    WARMINSKO_MAZURSKIE_GIZYCKI_RYN_MIEJSKO_WIEJSKA = ('2806083', 'Ryn', GminaType.MIEJSKO_WIEJSKA,
                                                       'warmińsko-mazurskie', 'giżycki', 'powiat')
    WARMINSKO_MAZURSKIE_GIZYCKI_WYDMINY_WIEJSKA = ('2806102', 'Wydminy', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                   'giżycki', 'powiat')
    WARMINSKO_MAZURSKIE_ILAWSKI_ILAWA_MIEJSKA = ('2807011', 'Iława', GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                 'iławski', 'powiat')
    WARMINSKO_MAZURSKIE_ILAWSKI_LUBAWA_MIEJSKA = ('2807021', 'Lubawa', GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                  'iławski', 'powiat')
    WARMINSKO_MAZURSKIE_ILAWSKI_ILAWA_WIEJSKA = ('2807032', 'Iława', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                 'iławski', 'powiat')
    WARMINSKO_MAZURSKIE_ILAWSKI_KISIELICE_MIEJSKO_WIEJSKA = ('2807043', 'Kisielice', GminaType.MIEJSKO_WIEJSKA,
                                                             'warmińsko-mazurskie', 'iławski', 'powiat')
    WARMINSKO_MAZURSKIE_ILAWSKI_LUBAWA_WIEJSKA = ('2807052', 'Lubawa', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                  'iławski', 'powiat')
    WARMINSKO_MAZURSKIE_ILAWSKI_SUSZ_MIEJSKO_WIEJSKA = ('2807063', 'Susz', GminaType.MIEJSKO_WIEJSKA,
                                                        'warmińsko-mazurskie', 'iławski', 'powiat')
    WARMINSKO_MAZURSKIE_ILAWSKI_ZALEWO_MIEJSKO_WIEJSKA = ('2807073', 'Zalewo', GminaType.MIEJSKO_WIEJSKA,
                                                          'warmińsko-mazurskie', 'iławski', 'powiat')
    WARMINSKO_MAZURSKIE_KETRZYNSKI_KETRZYN_MIEJSKA = ('2808011', 'Kętrzyn', GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                      'kętrzyński', 'powiat')
    WARMINSKO_MAZURSKIE_KETRZYNSKI_BARCIANY_WIEJSKA = ('2808022', 'Barciany', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                       'kętrzyński', 'powiat')
    WARMINSKO_MAZURSKIE_KETRZYNSKI_KETRZYN_WIEJSKA = ('2808032', 'Kętrzyn', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                      'kętrzyński', 'powiat')
    WARMINSKO_MAZURSKIE_KETRZYNSKI_KORSZE_MIEJSKO_WIEJSKA = ('2808043', 'Korsze', GminaType.MIEJSKO_WIEJSKA,
                                                             'warmińsko-mazurskie', 'kętrzyński', 'powiat')
    WARMINSKO_MAZURSKIE_KETRZYNSKI_RESZEL_MIEJSKO_WIEJSKA = ('2808053', 'Reszel', GminaType.MIEJSKO_WIEJSKA,
                                                             'warmińsko-mazurskie', 'kętrzyński', 'powiat')
    WARMINSKO_MAZURSKIE_KETRZYNSKI_SROKOWO_WIEJSKA = ('2808062', 'Srokowo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                      'kętrzyński', 'powiat')
    WARMINSKO_MAZURSKIE_LIDZBARSKI_LIDZBARK_WARMINSKI_MIEJSKA = ('2809011', 'Lidzbark Warmiński', GminaType.MIEJSKA,
                                                                 'warmińsko-mazurskie', 'lidzbarski', 'powiat')
    WARMINSKO_MAZURSKIE_LIDZBARSKI_KIWITY_WIEJSKA = ('2809022', 'Kiwity', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'lidzbarski', 'powiat')
    WARMINSKO_MAZURSKIE_LIDZBARSKI_LIDZBARK_WARMINSKI_WIEJSKA = ('2809032', 'Lidzbark Warmiński', GminaType.WIEJSKA,
                                                                 'warmińsko-mazurskie', 'lidzbarski', 'powiat')
    WARMINSKO_MAZURSKIE_LIDZBARSKI_LUBOMINO_WIEJSKA = ('2809042', 'Lubomino', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                       'lidzbarski', 'powiat')
    WARMINSKO_MAZURSKIE_LIDZBARSKI_ORNETA_MIEJSKO_WIEJSKA = ('2809053', 'Orneta', GminaType.MIEJSKO_WIEJSKA,
                                                             'warmińsko-mazurskie', 'lidzbarski', 'powiat')
    WARMINSKO_MAZURSKIE_MRAGOWSKI_MRAGOWO_MIEJSKA = ('2810011', 'Mrągowo', GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                     'mrągowski', 'powiat')
    WARMINSKO_MAZURSKIE_MRAGOWSKI_MIKOLAJKI_MIEJSKO_WIEJSKA = ('2810023', 'Mikołajki', GminaType.MIEJSKO_WIEJSKA,
                                                               'warmińsko-mazurskie', 'mrągowski', 'powiat')
    WARMINSKO_MAZURSKIE_MRAGOWSKI_MRAGOWO_WIEJSKA = ('2810032', 'Mrągowo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'mrągowski', 'powiat')
    WARMINSKO_MAZURSKIE_MRAGOWSKI_PIECKI_WIEJSKA = ('2810042', 'Piecki', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                    'mrągowski', 'powiat')
    WARMINSKO_MAZURSKIE_MRAGOWSKI_SORKWITY_WIEJSKA = ('2810052', 'Sorkwity', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                      'mrągowski', 'powiat')
    WARMINSKO_MAZURSKIE_NIDZICKI_JANOWIEC_KOSCIELNY_WIEJSKA = ('2811012', 'Janowiec Kościelny', GminaType.WIEJSKA,
                                                               'warmińsko-mazurskie', 'nidzicki', 'powiat')
    WARMINSKO_MAZURSKIE_NIDZICKI_JANOWO_WIEJSKA = ('2811022', 'Janowo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                   'nidzicki', 'powiat')
    WARMINSKO_MAZURSKIE_NIDZICKI_KOZLOWO_WIEJSKA = ('2811032', 'Kozłowo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                    'nidzicki', 'powiat')
    WARMINSKO_MAZURSKIE_NIDZICKI_NIDZICA_MIEJSKO_WIEJSKA = ('2811043', 'Nidzica', GminaType.MIEJSKO_WIEJSKA,
                                                            'warmińsko-mazurskie', 'nidzicki', 'powiat')
    WARMINSKO_MAZURSKIE_NOWOMIEJSKI_NOWE_MIASTO_LUBAWSKIE_MIEJSKA = ('2812011', 'Nowe Miasto Lubawskie',
                                                                     GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                                     'nowomiejski', 'powiat')
    WARMINSKO_MAZURSKIE_NOWOMIEJSKI_BISKUPIEC_WIEJSKA = ('2812022', 'Biskupiec', GminaType.WIEJSKA,
                                                         'warmińsko-mazurskie', 'nowomiejski', 'powiat')
    WARMINSKO_MAZURSKIE_NOWOMIEJSKI_GRODZICZNO_WIEJSKA = ('2812032', 'Grodziczno', GminaType.WIEJSKA,
                                                          'warmińsko-mazurskie', 'nowomiejski', 'powiat')
    WARMINSKO_MAZURSKIE_NOWOMIEJSKI_KURZETNIK_WIEJSKA = ('2812042', 'Kurzętnik', GminaType.WIEJSKA,
                                                         'warmińsko-mazurskie', 'nowomiejski', 'powiat')
    WARMINSKO_MAZURSKIE_NOWOMIEJSKI_BRATIAN_WIEJSKA = ('2812052', 'Bratian', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                       'nowomiejski', 'powiat')
    WARMINSKO_MAZURSKIE_OLECKI_KOWALE_OLECKIE_WIEJSKA = ('2813032', 'Kowale Oleckie', GminaType.WIEJSKA,
                                                         'warmińsko-mazurskie', 'olecki', 'powiat')
    WARMINSKO_MAZURSKIE_OLECKI_OLECKO_MIEJSKO_WIEJSKA = ('2813043', 'Olecko', GminaType.MIEJSKO_WIEJSKA,
                                                         'warmińsko-mazurskie', 'olecki', 'powiat')
    WARMINSKO_MAZURSKIE_OLECKI_SWIETAJNO_WIEJSKA = ('2813052', 'Świętajno', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                    'olecki', 'powiat')
    WARMINSKO_MAZURSKIE_OLECKI_WIELICZKI_WIEJSKA = ('2813062', 'Wieliczki', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                    'olecki', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_BARCZEWO_MIEJSKO_WIEJSKA = ('2814013', 'Barczewo', GminaType.MIEJSKO_WIEJSKA,
                                                               'warmińsko-mazurskie', 'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_BISKUPIEC_MIEJSKO_WIEJSKA = ('2814023', 'Biskupiec', GminaType.MIEJSKO_WIEJSKA,
                                                                'warmińsko-mazurskie', 'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_DOBRE_MIASTO_MIEJSKO_WIEJSKA = ('2814033', 'Dobre Miasto', GminaType.MIEJSKO_WIEJSKA,
                                                                   'warmińsko-mazurskie', 'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_DYWITY_WIEJSKA = ('2814042', 'Dywity', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_GIETRZWALD_WIEJSKA = ('2814052', 'Gietrzwałd', GminaType.WIEJSKA,
                                                         'warmińsko-mazurskie', 'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_JEZIORANY_MIEJSKO_WIEJSKA = ('2814063', 'Jeziorany', GminaType.MIEJSKO_WIEJSKA,
                                                                'warmińsko-mazurskie', 'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_JONKOWO_WIEJSKA = ('2814072', 'Jonkowo', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                      'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_KOLNO_WIEJSKA = ('2814082', 'Kolno', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                    'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_OLSZTYNEK_MIEJSKO_WIEJSKA = ('2814093', 'Olsztynek', GminaType.MIEJSKO_WIEJSKA,
                                                                'warmińsko-mazurskie', 'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_PURDA_WIEJSKA = ('2814102', 'Purda', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                    'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_STAWIGUDA_WIEJSKA = ('2814112', 'Stawiguda', GminaType.WIEJSKA,
                                                        'warmińsko-mazurskie', 'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OLSZTYNSKI_SWIATKI_WIEJSKA = ('2814122', 'Świątki', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                      'olsztyński', 'powiat')
    WARMINSKO_MAZURSKIE_OSTRODZKI_OSTRODA_MIEJSKA = ('2815011', 'Ostróda', GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                     'ostródzki', 'powiat')
    WARMINSKO_MAZURSKIE_OSTRODZKI_DABROWNO_WIEJSKA = ('2815022', 'Dąbrówno', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                      'ostródzki', 'powiat')
    WARMINSKO_MAZURSKIE_OSTRODZKI_GRUNWALD_WIEJSKA = ('2815032', 'Grunwald', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                      'ostródzki', 'powiat')
    WARMINSKO_MAZURSKIE_OSTRODZKI_LUKTA_WIEJSKA = ('2815042', 'Łukta', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                   'ostródzki', 'powiat')
    WARMINSKO_MAZURSKIE_OSTRODZKI_MALDYTY_WIEJSKA = ('2815052', 'Małdyty', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'ostródzki', 'powiat')
    WARMINSKO_MAZURSKIE_OSTRODZKI_MILAKOWO_MIEJSKO_WIEJSKA = ('2815063', 'Miłakowo', GminaType.MIEJSKO_WIEJSKA,
                                                              'warmińsko-mazurskie', 'ostródzki', 'powiat')
    WARMINSKO_MAZURSKIE_OSTRODZKI_MILOMLYN_MIEJSKO_WIEJSKA = ('2815073', 'Miłomłyn', GminaType.MIEJSKO_WIEJSKA,
                                                              'warmińsko-mazurskie', 'ostródzki', 'powiat')
    WARMINSKO_MAZURSKIE_OSTRODZKI_MORAG_MIEJSKO_WIEJSKA = ('2815083', 'Morąg', GminaType.MIEJSKO_WIEJSKA,
                                                           'warmińsko-mazurskie', 'ostródzki', 'powiat')
    WARMINSKO_MAZURSKIE_OSTRODZKI_OSTRODA_WIEJSKA = ('2815092', 'Ostróda', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'ostródzki', 'powiat')
    WARMINSKO_MAZURSKIE_PISKI_BIALA_PISKA_MIEJSKO_WIEJSKA = ('2816013', 'Biała Piska', GminaType.MIEJSKO_WIEJSKA,
                                                             'warmińsko-mazurskie', 'piski', 'powiat')
    WARMINSKO_MAZURSKIE_PISKI_ORZYSZ_MIEJSKO_WIEJSKA = ('2816023', 'Orzysz', GminaType.MIEJSKO_WIEJSKA,
                                                        'warmińsko-mazurskie', 'piski', 'powiat')
    WARMINSKO_MAZURSKIE_PISKI_PISZ_MIEJSKO_WIEJSKA = ('2816033', 'Pisz', GminaType.MIEJSKO_WIEJSKA,
                                                      'warmińsko-mazurskie', 'piski', 'powiat')
    WARMINSKO_MAZURSKIE_PISKI_RUCIANE_NIDA_MIEJSKO_WIEJSKA = ('2816043', 'Ruciane-Nida', GminaType.MIEJSKO_WIEJSKA,
                                                              'warmińsko-mazurskie', 'piski', 'powiat')
    WARMINSKO_MAZURSKIE_SZCZYCIENSKI_SZCZYTNO_MIEJSKA = ('2817011', 'Szczytno', GminaType.MIEJSKA,
                                                         'warmińsko-mazurskie', 'szczycieński', 'powiat')
    WARMINSKO_MAZURSKIE_SZCZYCIENSKI_DZWIERZUTY_WIEJSKA = ('2817022', 'Dźwierzuty', GminaType.WIEJSKA,
                                                           'warmińsko-mazurskie', 'szczycieński', 'powiat')
    WARMINSKO_MAZURSKIE_SZCZYCIENSKI_JEDWABNO_WIEJSKA = ('2817032', 'Jedwabno', GminaType.WIEJSKA,
                                                         'warmińsko-mazurskie', 'szczycieński', 'powiat')
    WARMINSKO_MAZURSKIE_SZCZYCIENSKI_PASYM_MIEJSKO_WIEJSKA = ('2817043', 'Pasym', GminaType.MIEJSKO_WIEJSKA,
                                                              'warmińsko-mazurskie', 'szczycieński', 'powiat')
    WARMINSKO_MAZURSKIE_SZCZYCIENSKI_ROZOGI_WIEJSKA = ('2817052', 'Rozogi', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                       'szczycieński', 'powiat')
    WARMINSKO_MAZURSKIE_SZCZYCIENSKI_SZCZYTNO_WIEJSKA = ('2817062', 'Szczytno', GminaType.WIEJSKA,
                                                         'warmińsko-mazurskie', 'szczycieński', 'powiat')
    WARMINSKO_MAZURSKIE_SZCZYCIENSKI_SWIETAJNO_WIEJSKA = ('2817072', 'Świętajno', GminaType.WIEJSKA,
                                                          'warmińsko-mazurskie', 'szczycieński', 'powiat')
    WARMINSKO_MAZURSKIE_SZCZYCIENSKI_WIELBARK_MIEJSKO_WIEJSKA = ('2817083', 'Wielbark', GminaType.MIEJSKO_WIEJSKA,
                                                                 'warmińsko-mazurskie', 'szczycieński', 'powiat')
    WARMINSKO_MAZURSKIE_GOLDAPSKI_BANIE_MAZURSKIE_WIEJSKA = ('2818012', 'Banie Mazurskie', GminaType.WIEJSKA,
                                                             'warmińsko-mazurskie', 'gołdapski', 'powiat')
    WARMINSKO_MAZURSKIE_GOLDAPSKI_DUBENINKI_WIEJSKA = ('2818022', 'Dubeninki', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                       'gołdapski', 'powiat')
    WARMINSKO_MAZURSKIE_GOLDAPSKI_GOLDAP_MIEJSKO_WIEJSKA = ('2818033', 'Gołdap', GminaType.MIEJSKO_WIEJSKA,
                                                            'warmińsko-mazurskie', 'gołdapski', 'powiat')
    WARMINSKO_MAZURSKIE_WEGORZEWSKI_BUDRY_WIEJSKA = ('2819012', 'Budry', GminaType.WIEJSKA, 'warmińsko-mazurskie',
                                                     'węgorzewski', 'powiat')
    WARMINSKO_MAZURSKIE_WEGORZEWSKI_POZEZDRZE_WIEJSKA = ('2819022', 'Pozezdrze', GminaType.WIEJSKA,
                                                         'warmińsko-mazurskie', 'węgorzewski', 'powiat')
    WARMINSKO_MAZURSKIE_WEGORZEWSKI_WEGORZEWO_MIEJSKO_WIEJSKA = ('2819033', 'Węgorzewo', GminaType.MIEJSKO_WIEJSKA,
                                                                 'warmińsko-mazurskie', 'węgorzewski', 'powiat')
    WARMINSKO_MAZURSKIE_ELBLAG_ELBLAG_MIEJSKA = ('2861011', 'Elbląg', GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                 'Elbląg', 'miasto na prawach powiatu')
    WARMINSKO_MAZURSKIE_OLSZTYN_OLSZTYN_MIEJSKA = ('2862011', 'Olsztyn', GminaType.MIEJSKA, 'warmińsko-mazurskie',
                                                   'Olsztyn', 'miasto na prawach powiatu')

    # Wielkopolskie
    WIELKOPOLSKIE_CHODZIESKI_CHODZIEZ_MIEJSKA = ('3001011', 'Chodzież', GminaType.MIEJSKA, 'wielkopolskie',
                                                 'chodzieski', 'powiat')
    WIELKOPOLSKIE_CHODZIESKI_BUDZYN_MIEJSKO_WIEJSKA = ('3001023', 'Budzyń', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                       'chodzieski', 'powiat')
    WIELKOPOLSKIE_CHODZIESKI_CHODZIEZ_WIEJSKA = ('3001032', 'Chodzież', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'chodzieski', 'powiat')
    WIELKOPOLSKIE_CHODZIESKI_MARGONIN_MIEJSKO_WIEJSKA = ('3001043', 'Margonin', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'chodzieski', 'powiat')
    WIELKOPOLSKIE_CHODZIESKI_SZAMOCIN_MIEJSKO_WIEJSKA = ('3001053', 'Szamocin', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'chodzieski', 'powiat')
    WIELKOPOLSKIE_CZARNKOWSKO_TRZCIANECKI_CZARNKOW_MIEJSKA = ('3002011', 'Czarnków', GminaType.MIEJSKA, 'wielkopolskie',
                                                              'czarnkowsko-trzcianecki', 'powiat')
    WIELKOPOLSKIE_CZARNKOWSKO_TRZCIANECKI_CZARNKOW_WIEJSKA = ('3002022', 'Czarnków', GminaType.WIEJSKA, 'wielkopolskie',
                                                              'czarnkowsko-trzcianecki', 'powiat')
    WIELKOPOLSKIE_CZARNKOWSKO_TRZCIANECKI_DRAWSKO_WIEJSKA = ('3002032', 'Drawsko', GminaType.WIEJSKA, 'wielkopolskie',
                                                             'czarnkowsko-trzcianecki', 'powiat')
    WIELKOPOLSKIE_CZARNKOWSKO_TRZCIANECKI_KRZYZ_WIELKOPOLSKI_MIEJSKO_WIEJSKA = ('3002043', 'Krzyż Wielkopolski',
                                                                                GminaType.MIEJSKO_WIEJSKA,
                                                                                'wielkopolskie',
                                                                                'czarnkowsko-trzcianecki', 'powiat')
    WIELKOPOLSKIE_CZARNKOWSKO_TRZCIANECKI_LUBASZ_WIEJSKA = ('3002052', 'Lubasz', GminaType.WIEJSKA, 'wielkopolskie',
                                                            'czarnkowsko-trzcianecki', 'powiat')
    WIELKOPOLSKIE_CZARNKOWSKO_TRZCIANECKI_POLAJEWO_WIEJSKA = ('3002062', 'Połajewo', GminaType.WIEJSKA, 'wielkopolskie',
                                                              'czarnkowsko-trzcianecki', 'powiat')
    WIELKOPOLSKIE_CZARNKOWSKO_TRZCIANECKI_TRZCIANKA_MIEJSKO_WIEJSKA = ('3002073', 'Trzcianka',
                                                                       GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                                       'czarnkowsko-trzcianecki', 'powiat')
    WIELKOPOLSKIE_CZARNKOWSKO_TRZCIANECKI_WIELEN_MIEJSKO_WIEJSKA = ('3002083', 'Wieleń', GminaType.MIEJSKO_WIEJSKA,
                                                                    'wielkopolskie', 'czarnkowsko-trzcianecki',
                                                                    'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_GNIEZNO_MIEJSKA = ('3003011', 'Gniezno', GminaType.MIEJSKA, 'wielkopolskie',
                                                  'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_CZERNIEJEWO_MIEJSKO_WIEJSKA = ('3003023', 'Czerniejewo', GminaType.MIEJSKO_WIEJSKA,
                                                              'wielkopolskie', 'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_GNIEZNO_WIEJSKA = ('3003032', 'Gniezno', GminaType.WIEJSKA, 'wielkopolskie',
                                                  'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_KISZKOWO_WIEJSKA = ('3003042', 'Kiszkowo', GminaType.WIEJSKA, 'wielkopolskie',
                                                   'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_KLECKO_MIEJSKO_WIEJSKA = ('3003053', 'Kłecko', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_LUBOWO_WIEJSKA = ('3003062', 'Łubowo', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_MIELESZYN_WIEJSKA = ('3003072', 'Mieleszyn', GminaType.WIEJSKA, 'wielkopolskie',
                                                    'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_NIECHANOWO_WIEJSKA = ('3003082', 'Niechanowo', GminaType.WIEJSKA, 'wielkopolskie',
                                                     'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_TRZEMESZNO_MIEJSKO_WIEJSKA = ('3003093', 'Trzemeszno', GminaType.MIEJSKO_WIEJSKA,
                                                             'wielkopolskie', 'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GNIEZNIENSKI_WITKOWO_MIEJSKO_WIEJSKA = ('3003103', 'Witkowo', GminaType.MIEJSKO_WIEJSKA,
                                                          'wielkopolskie', 'gnieźnieński', 'powiat')
    WIELKOPOLSKIE_GOSTYNSKI_BOREK_WIELKOPOLSKI_MIEJSKO_WIEJSKA = ('3004013', 'Borek Wielkopolski',
                                                                  GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                                  'gostyński', 'powiat')
    WIELKOPOLSKIE_GOSTYNSKI_GOSTYN_MIEJSKO_WIEJSKA = ('3004023', 'Gostyń', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'gostyński', 'powiat')
    WIELKOPOLSKIE_GOSTYNSKI_KROBIA_MIEJSKO_WIEJSKA = ('3004033', 'Krobia', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'gostyński', 'powiat')
    WIELKOPOLSKIE_GOSTYNSKI_PEPOWO_WIEJSKA = ('3004042', 'Pępowo', GminaType.WIEJSKA, 'wielkopolskie', 'gostyński',
                                              'powiat')
    WIELKOPOLSKIE_GOSTYNSKI_PIASKI_WIEJSKA = ('3004052', 'Piaski', GminaType.WIEJSKA, 'wielkopolskie', 'gostyński',
                                              'powiat')
    WIELKOPOLSKIE_GOSTYNSKI_POGORZELA_MIEJSKO_WIEJSKA = ('3004063', 'Pogorzela', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'gostyński', 'powiat')
    WIELKOPOLSKIE_GOSTYNSKI_PONIEC_MIEJSKO_WIEJSKA = ('3004073', 'Poniec', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'gostyński', 'powiat')
    WIELKOPOLSKIE_GRODZISKI_GRANOWO_WIEJSKA = ('3005012', 'Granowo', GminaType.WIEJSKA, 'wielkopolskie', 'grodziski',
                                               'powiat')
    WIELKOPOLSKIE_GRODZISKI_GRODZISK_WIELKOPOLSKI_MIEJSKO_WIEJSKA = ('3005023', 'Grodzisk Wielkopolski',
                                                                     GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                                     'grodziski', 'powiat')
    WIELKOPOLSKIE_GRODZISKI_KAMIENIEC_WIEJSKA = ('3005032', 'Kamieniec', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'grodziski', 'powiat')
    WIELKOPOLSKIE_GRODZISKI_RAKONIEWICE_MIEJSKO_WIEJSKA = ('3005043', 'Rakoniewice', GminaType.MIEJSKO_WIEJSKA,
                                                           'wielkopolskie', 'grodziski', 'powiat')
    WIELKOPOLSKIE_GRODZISKI_WIELICHOWO_MIEJSKO_WIEJSKA = ('3005053', 'Wielichowo', GminaType.MIEJSKO_WIEJSKA,
                                                          'wielkopolskie', 'grodziski', 'powiat')
    WIELKOPOLSKIE_JAROCINSKI_JARACZEWO_MIEJSKO_WIEJSKA = ('3006013', 'Jaraczewo', GminaType.MIEJSKO_WIEJSKA,
                                                          'wielkopolskie', 'jarociński', 'powiat')
    WIELKOPOLSKIE_JAROCINSKI_JAROCIN_MIEJSKO_WIEJSKA = ('3006023', 'Jarocin', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'jarociński', 'powiat')
    WIELKOPOLSKIE_JAROCINSKI_KOTLIN_WIEJSKA = ('3006032', 'Kotlin', GminaType.WIEJSKA, 'wielkopolskie', 'jarociński',
                                               'powiat')
    WIELKOPOLSKIE_JAROCINSKI_ZERKOW_MIEJSKO_WIEJSKA = ('3006043', 'Żerków', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                       'jarociński', 'powiat')
    WIELKOPOLSKIE_KALISKI_BLIZANOW_WIEJSKA = ('3007012', 'Blizanów', GminaType.WIEJSKA, 'wielkopolskie', 'kaliski',
                                              'powiat')
    WIELKOPOLSKIE_KALISKI_BRZEZINY_WIEJSKA = ('3007022', 'Brzeziny', GminaType.WIEJSKA, 'wielkopolskie', 'kaliski',
                                              'powiat')
    WIELKOPOLSKIE_KALISKI_CEKOW_KOLONIA_WIEJSKA = ('3007032', 'Ceków-Kolonia', GminaType.WIEJSKA, 'wielkopolskie',
                                                   'kaliski', 'powiat')
    WIELKOPOLSKIE_KALISKI_GODZIESZE_WIELKIE_WIEJSKA = ('3007042', 'Godziesze Wielkie', GminaType.WIEJSKA,
                                                       'wielkopolskie', 'kaliski', 'powiat')
    WIELKOPOLSKIE_KALISKI_KOZMINEK_MIEJSKO_WIEJSKA = ('3007053', 'Koźminek', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'kaliski', 'powiat')
    WIELKOPOLSKIE_KALISKI_LISKOW_WIEJSKA = ('3007062', 'Lisków', GminaType.WIEJSKA, 'wielkopolskie', 'kaliski',
                                            'powiat')
    WIELKOPOLSKIE_KALISKI_MYCIELIN_WIEJSKA = ('3007072', 'Mycielin', GminaType.WIEJSKA, 'wielkopolskie', 'kaliski',
                                              'powiat')
    WIELKOPOLSKIE_KALISKI_OPATOWEK_MIEJSKO_WIEJSKA = ('3007083', 'Opatówek', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'kaliski', 'powiat')
    WIELKOPOLSKIE_KALISKI_STAWISZYN_MIEJSKO_WIEJSKA = ('3007093', 'Stawiszyn', GminaType.MIEJSKO_WIEJSKA,
                                                       'wielkopolskie', 'kaliski', 'powiat')
    WIELKOPOLSKIE_KALISKI_SZCZYTNIKI_WIEJSKA = ('3007102', 'Szczytniki', GminaType.WIEJSKA, 'wielkopolskie', 'kaliski',
                                                'powiat')
    WIELKOPOLSKIE_KALISKI_ZELAZKOW_WIEJSKA = ('3007112', 'Żelazków', GminaType.WIEJSKA, 'wielkopolskie', 'kaliski',
                                              'powiat')
    WIELKOPOLSKIE_KEPINSKI_BARANOW_WIEJSKA = ('3008012', 'Baranów', GminaType.WIEJSKA, 'wielkopolskie', 'kępiński',
                                              'powiat')
    WIELKOPOLSKIE_KEPINSKI_BRALIN_WIEJSKA = ('3008022', 'Bralin', GminaType.WIEJSKA, 'wielkopolskie', 'kępiński',
                                             'powiat')
    WIELKOPOLSKIE_KEPINSKI_KEPNO_MIEJSKO_WIEJSKA = ('3008033', 'Kępno', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                    'kępiński', 'powiat')
    WIELKOPOLSKIE_KEPINSKI_LEKA_OPATOWSKA_WIEJSKA = ('3008042', 'Łęka Opatowska', GminaType.WIEJSKA, 'wielkopolskie',
                                                     'kępiński', 'powiat')
    WIELKOPOLSKIE_KEPINSKI_PERZOW_WIEJSKA = ('3008052', 'Perzów', GminaType.WIEJSKA, 'wielkopolskie', 'kępiński',
                                             'powiat')
    WIELKOPOLSKIE_KEPINSKI_RYCHTAL_MIEJSKO_WIEJSKA = ('3008063', 'Rychtal', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'kępiński', 'powiat')
    WIELKOPOLSKIE_KEPINSKI_TRZCINICA_WIEJSKA = ('3008072', 'Trzcinica', GminaType.WIEJSKA, 'wielkopolskie', 'kępiński',
                                                'powiat')
    WIELKOPOLSKIE_KOLSKI_KOLO_MIEJSKA = ('3009011', 'Koło', GminaType.MIEJSKA, 'wielkopolskie', 'kolski', 'powiat')
    WIELKOPOLSKIE_KOLSKI_BABIAK_WIEJSKA = ('3009022', 'Babiak', GminaType.WIEJSKA, 'wielkopolskie', 'kolski', 'powiat')
    WIELKOPOLSKIE_KOLSKI_CHODOW_WIEJSKA = ('3009032', 'Chodów', GminaType.WIEJSKA, 'wielkopolskie', 'kolski', 'powiat')
    WIELKOPOLSKIE_KOLSKI_DABIE_MIEJSKO_WIEJSKA = ('3009043', 'Dąbie', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                  'kolski', 'powiat')
    WIELKOPOLSKIE_KOLSKI_GRZEGORZEW_WIEJSKA = ('3009052', 'Grzegorzew', GminaType.WIEJSKA, 'wielkopolskie', 'kolski',
                                               'powiat')
    WIELKOPOLSKIE_KOLSKI_KLODAWA_MIEJSKO_WIEJSKA = ('3009063', 'Kłodawa', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                    'kolski', 'powiat')
    WIELKOPOLSKIE_KOLSKI_KOLO_WIEJSKA = ('3009072', 'Koło', GminaType.WIEJSKA, 'wielkopolskie', 'kolski', 'powiat')
    WIELKOPOLSKIE_KOLSKI_KOSCIELEC_WIEJSKA = ('3009082', 'Kościelec', GminaType.WIEJSKA, 'wielkopolskie', 'kolski',
                                              'powiat')
    WIELKOPOLSKIE_KOLSKI_OLSZOWKA_WIEJSKA = ('3009092', 'Olszówka', GminaType.WIEJSKA, 'wielkopolskie', 'kolski',
                                             'powiat')
    WIELKOPOLSKIE_KOLSKI_OSIEK_MALY_WIEJSKA = ('3009102', 'Osiek Mały', GminaType.WIEJSKA, 'wielkopolskie', 'kolski',
                                               'powiat')
    WIELKOPOLSKIE_KOLSKI_PRZEDECZ_MIEJSKO_WIEJSKA = ('3009113', 'Przedecz', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                     'kolski', 'powiat')
    WIELKOPOLSKIE_KONINSKI_GOLINA_MIEJSKO_WIEJSKA = ('3010013', 'Golina', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                     'koniński', 'powiat')
    WIELKOPOLSKIE_KONINSKI_GRODZIEC_WIEJSKA = ('3010022', 'Grodziec', GminaType.WIEJSKA, 'wielkopolskie', 'koniński',
                                               'powiat')
    WIELKOPOLSKIE_KONINSKI_KAZIMIERZ_BISKUPI_WIEJSKA = ('3010032', 'Kazimierz Biskupi', GminaType.WIEJSKA,
                                                        'wielkopolskie', 'koniński', 'powiat')
    WIELKOPOLSKIE_KONINSKI_KLECZEW_MIEJSKO_WIEJSKA = ('3010043', 'Kleczew', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'koniński', 'powiat')
    WIELKOPOLSKIE_KONINSKI_KRAMSK_WIEJSKA = ('3010052', 'Kramsk', GminaType.WIEJSKA, 'wielkopolskie', 'koniński',
                                             'powiat')
    WIELKOPOLSKIE_KONINSKI_KRZYMOW_WIEJSKA = ('3010062', 'Krzymów', GminaType.WIEJSKA, 'wielkopolskie', 'koniński',
                                              'powiat')
    WIELKOPOLSKIE_KONINSKI_RYCHWAL_MIEJSKO_WIEJSKA = ('3010073', 'Rychwał', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'koniński', 'powiat')
    WIELKOPOLSKIE_KONINSKI_RZGOW_WIEJSKA = ('3010082', 'Rzgów', GminaType.WIEJSKA, 'wielkopolskie', 'koniński',
                                            'powiat')
    WIELKOPOLSKIE_KONINSKI_SKULSK_WIEJSKA = ('3010092', 'Skulsk', GminaType.WIEJSKA, 'wielkopolskie', 'koniński',
                                             'powiat')
    WIELKOPOLSKIE_KONINSKI_SOMPOLNO_MIEJSKO_WIEJSKA = ('3010103', 'Sompolno', GminaType.MIEJSKO_WIEJSKA,
                                                       'wielkopolskie', 'koniński', 'powiat')
    WIELKOPOLSKIE_KONINSKI_STARE_MIASTO_WIEJSKA = ('3010112', 'Stare Miasto', GminaType.WIEJSKA, 'wielkopolskie',
                                                   'koniński', 'powiat')
    WIELKOPOLSKIE_KONINSKI_SLESIN_MIEJSKO_WIEJSKA = ('3010123', 'Ślesin', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                     'koniński', 'powiat')
    WIELKOPOLSKIE_KONINSKI_WIERZBINEK_WIEJSKA = ('3010132', 'Wierzbinek', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'koniński', 'powiat')
    WIELKOPOLSKIE_KONINSKI_WILCZYN_WIEJSKA = ('3010142', 'Wilczyn', GminaType.WIEJSKA, 'wielkopolskie', 'koniński',
                                              'powiat')
    WIELKOPOLSKIE_KOSCIANSKI_KOSCIAN_MIEJSKA = ('3011011', 'Kościan', GminaType.MIEJSKA, 'wielkopolskie', 'kościański',
                                                'powiat')
    WIELKOPOLSKIE_KOSCIANSKI_CZEMPIN_MIEJSKO_WIEJSKA = ('3011023', 'Czempiń', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'kościański', 'powiat')
    WIELKOPOLSKIE_KOSCIANSKI_KOSCIAN_WIEJSKA = ('3011032', 'Kościan', GminaType.WIEJSKA, 'wielkopolskie', 'kościański',
                                                'powiat')
    WIELKOPOLSKIE_KOSCIANSKI_KRZYWIN_MIEJSKO_WIEJSKA = ('3011043', 'Krzywiń', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'kościański', 'powiat')
    WIELKOPOLSKIE_KOSCIANSKI_SMIGIEL_MIEJSKO_WIEJSKA = ('3011053', 'Śmigiel', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'kościański', 'powiat')
    WIELKOPOLSKIE_KROTOSZYNSKI_SULMIERZYCE_MIEJSKA = ('3012011', 'Sulmierzyce', GminaType.MIEJSKA, 'wielkopolskie',
                                                      'krotoszyński', 'powiat')
    WIELKOPOLSKIE_KROTOSZYNSKI_KOBYLIN_MIEJSKO_WIEJSKA = ('3012023', 'Kobylin', GminaType.MIEJSKO_WIEJSKA,
                                                          'wielkopolskie', 'krotoszyński', 'powiat')
    WIELKOPOLSKIE_KROTOSZYNSKI_KOZMIN_WIELKOPOLSKI_MIEJSKO_WIEJSKA = ('3012033', 'Koźmin Wielkopolski',
                                                                      GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                                      'krotoszyński', 'powiat')
    WIELKOPOLSKIE_KROTOSZYNSKI_KROTOSZYN_MIEJSKO_WIEJSKA = ('3012043', 'Krotoszyn', GminaType.MIEJSKO_WIEJSKA,
                                                            'wielkopolskie', 'krotoszyński', 'powiat')
    WIELKOPOLSKIE_KROTOSZYNSKI_ROZDRAZEW_WIEJSKA = ('3012052', 'Rozdrażew', GminaType.WIEJSKA, 'wielkopolskie',
                                                    'krotoszyński', 'powiat')
    WIELKOPOLSKIE_KROTOSZYNSKI_ZDUNY_MIEJSKO_WIEJSKA = ('3012063', 'Zduny', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                        'krotoszyński', 'powiat')
    WIELKOPOLSKIE_LESZCZYNSKI_KRZEMIENIEWO_WIEJSKA = ('3013012', 'Krzemieniewo', GminaType.WIEJSKA, 'wielkopolskie',
                                                      'leszczyński', 'powiat')
    WIELKOPOLSKIE_LESZCZYNSKI_LIPNO_WIEJSKA = ('3013022', 'Lipno', GminaType.WIEJSKA, 'wielkopolskie', 'leszczyński',
                                               'powiat')
    WIELKOPOLSKIE_LESZCZYNSKI_OSIECZNA_MIEJSKO_WIEJSKA = ('3013033', 'Osieczna', GminaType.MIEJSKO_WIEJSKA,
                                                          'wielkopolskie', 'leszczyński', 'powiat')
    WIELKOPOLSKIE_LESZCZYNSKI_RYDZYNA_MIEJSKO_WIEJSKA = ('3013043', 'Rydzyna', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'leszczyński', 'powiat')
    WIELKOPOLSKIE_LESZCZYNSKI_SWIECIECHOWA_WIEJSKA = ('3013052', 'Święciechowa', GminaType.WIEJSKA, 'wielkopolskie',
                                                      'leszczyński', 'powiat')
    WIELKOPOLSKIE_LESZCZYNSKI_WIJEWO_WIEJSKA = ('3013062', 'Wijewo', GminaType.WIEJSKA, 'wielkopolskie', 'leszczyński',
                                                'powiat')
    WIELKOPOLSKIE_LESZCZYNSKI_WLOSZAKOWICE_WIEJSKA = ('3013072', 'Włoszakowice', GminaType.WIEJSKA, 'wielkopolskie',
                                                      'leszczyński', 'powiat')
    WIELKOPOLSKIE_MIEDZYCHODZKI_CHRZYPSKO_WIELKIE_WIEJSKA = ('3014012', 'Chrzypsko Wielkie', GminaType.WIEJSKA,
                                                             'wielkopolskie', 'międzychodzki', 'powiat')
    WIELKOPOLSKIE_MIEDZYCHODZKI_KWILCZ_WIEJSKA = ('3014022', 'Kwilcz', GminaType.WIEJSKA, 'wielkopolskie',
                                                  'międzychodzki', 'powiat')
    WIELKOPOLSKIE_MIEDZYCHODZKI_MIEDZYCHOD_MIEJSKO_WIEJSKA = ('3014033', 'Międzychód', GminaType.MIEJSKO_WIEJSKA,
                                                              'wielkopolskie', 'międzychodzki', 'powiat')
    WIELKOPOLSKIE_MIEDZYCHODZKI_SIERAKOW_MIEJSKO_WIEJSKA = ('3014043', 'Sieraków', GminaType.MIEJSKO_WIEJSKA,
                                                            'wielkopolskie', 'międzychodzki', 'powiat')
    WIELKOPOLSKIE_NOWOTOMYSKI_KUSLIN_WIEJSKA = ('3015012', 'Kuślin', GminaType.WIEJSKA, 'wielkopolskie', 'nowotomyski',
                                                'powiat')
    WIELKOPOLSKIE_NOWOTOMYSKI_LWOWEK_MIEJSKO_WIEJSKA = ('3015023', 'Lwówek', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                        'nowotomyski', 'powiat')
    WIELKOPOLSKIE_NOWOTOMYSKI_MIEDZICHOWO_WIEJSKA = ('3015032', 'Miedzichowo', GminaType.WIEJSKA, 'wielkopolskie',
                                                     'nowotomyski', 'powiat')
    WIELKOPOLSKIE_NOWOTOMYSKI_NOWY_TOMYSL_MIEJSKO_WIEJSKA = ('3015043', 'Nowy Tomyśl', GminaType.MIEJSKO_WIEJSKA,
                                                             'wielkopolskie', 'nowotomyski', 'powiat')
    WIELKOPOLSKIE_NOWOTOMYSKI_OPALENICA_MIEJSKO_WIEJSKA = ('3015053', 'Opalenica', GminaType.MIEJSKO_WIEJSKA,
                                                           'wielkopolskie', 'nowotomyski', 'powiat')
    WIELKOPOLSKIE_NOWOTOMYSKI_ZBASZYN_MIEJSKO_WIEJSKA = ('3015063', 'Zbąszyń', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'nowotomyski', 'powiat')
    WIELKOPOLSKIE_OBORNICKI_OBORNIKI_MIEJSKO_WIEJSKA = ('3016013', 'Oborniki', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'obornicki', 'powiat')
    WIELKOPOLSKIE_OBORNICKI_ROGOZNO_MIEJSKO_WIEJSKA = ('3016023', 'Rogoźno', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                       'obornicki', 'powiat')
    WIELKOPOLSKIE_OBORNICKI_RYCZYWOL_WIEJSKA = ('3016032', 'Ryczywół', GminaType.WIEJSKA, 'wielkopolskie', 'obornicki',
                                                'powiat')
    WIELKOPOLSKIE_OSTROWSKI_OSTROW_WIELKOPOLSKI_MIEJSKA = ('3017011', 'Ostrów Wielkopolski', GminaType.MIEJSKA,
                                                           'wielkopolskie', 'ostrowski', 'powiat')
    WIELKOPOLSKIE_OSTROWSKI_NOWE_SKALMIERZYCE_MIEJSKO_WIEJSKA = ('3017023', 'Nowe Skalmierzyce',
                                                                 GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                                 'ostrowski', 'powiat')
    WIELKOPOLSKIE_OSTROWSKI_ODOLANOW_MIEJSKO_WIEJSKA = ('3017033', 'Odolanów', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'ostrowski', 'powiat')
    WIELKOPOLSKIE_OSTROWSKI_OSTROW_WIELKOPOLSKI_WIEJSKA = ('3017042', 'Ostrów Wielkopolski', GminaType.WIEJSKA,
                                                           'wielkopolskie', 'ostrowski', 'powiat')
    WIELKOPOLSKIE_OSTROWSKI_PRZYGODZICE_WIEJSKA = ('3017052', 'Przygodzice', GminaType.WIEJSKA, 'wielkopolskie',
                                                   'ostrowski', 'powiat')
    WIELKOPOLSKIE_OSTROWSKI_RASZKOW_MIEJSKO_WIEJSKA = ('3017063', 'Raszków', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                       'ostrowski', 'powiat')
    WIELKOPOLSKIE_OSTROWSKI_SIEROSZEWICE_WIEJSKA = ('3017072', 'Sieroszewice', GminaType.WIEJSKA, 'wielkopolskie',
                                                    'ostrowski', 'powiat')
    WIELKOPOLSKIE_OSTROWSKI_SOSNIE_WIEJSKA = ('3017082', 'Sośnie', GminaType.WIEJSKA, 'wielkopolskie', 'ostrowski',
                                              'powiat')
    WIELKOPOLSKIE_OSTRZESZOWSKI_CZAJKOW_WIEJSKA = ('3018012', 'Czajków', GminaType.WIEJSKA, 'wielkopolskie',
                                                   'ostrzeszowski', 'powiat')
    WIELKOPOLSKIE_OSTRZESZOWSKI_DORUCHOW_WIEJSKA = ('3018022', 'Doruchów', GminaType.WIEJSKA, 'wielkopolskie',
                                                    'ostrzeszowski', 'powiat')
    WIELKOPOLSKIE_OSTRZESZOWSKI_GRABOW_NAD_PROSNA_MIEJSKO_WIEJSKA = ('3018033', 'Grabów nad Prosną',
                                                                     GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                                     'ostrzeszowski', 'powiat')
    WIELKOPOLSKIE_OSTRZESZOWSKI_KOBYLA_GORA_WIEJSKA = ('3018042', 'Kobyla Góra', GminaType.WIEJSKA, 'wielkopolskie',
                                                       'ostrzeszowski', 'powiat')
    WIELKOPOLSKIE_OSTRZESZOWSKI_KRASZEWICE_WIEJSKA = ('3018052', 'Kraszewice', GminaType.WIEJSKA, 'wielkopolskie',
                                                      'ostrzeszowski', 'powiat')
    WIELKOPOLSKIE_OSTRZESZOWSKI_MIKSTAT_MIEJSKO_WIEJSKA = ('3018063', 'Mikstat', GminaType.MIEJSKO_WIEJSKA,
                                                           'wielkopolskie', 'ostrzeszowski', 'powiat')
    WIELKOPOLSKIE_OSTRZESZOWSKI_OSTRZESZOW_MIEJSKO_WIEJSKA = ('3018073', 'Ostrzeszów', GminaType.MIEJSKO_WIEJSKA,
                                                              'wielkopolskie', 'ostrzeszowski', 'powiat')
    WIELKOPOLSKIE_PILSKI_PILA_MIEJSKA = ('3019011', 'Piła', GminaType.MIEJSKA, 'wielkopolskie', 'pilski', 'powiat')
    WIELKOPOLSKIE_PILSKI_BIALOSLIWIE_WIEJSKA = ('3019022', 'Białośliwie', GminaType.WIEJSKA, 'wielkopolskie', 'pilski',
                                                'powiat')
    WIELKOPOLSKIE_PILSKI_KACZORY_MIEJSKO_WIEJSKA = ('3019033', 'Kaczory', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                    'pilski', 'powiat')
    WIELKOPOLSKIE_PILSKI_LOBZENICA_MIEJSKO_WIEJSKA = ('3019043', 'Łobżenica', GminaType.MIEJSKO_WIEJSKA,
                                                      'wielkopolskie', 'pilski', 'powiat')
    WIELKOPOLSKIE_PILSKI_MIASTECZKO_KRAJENSKIE_MIEJSKO_WIEJSKA = ('3019053', 'Miasteczko Krajeńskie',
                                                                  GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie', 'pilski',
                                                                  'powiat')
    WIELKOPOLSKIE_PILSKI_SZYDLOWO_WIEJSKA = ('3019062', 'Szydłowo', GminaType.WIEJSKA, 'wielkopolskie', 'pilski',
                                             'powiat')
    WIELKOPOLSKIE_PILSKI_UJSCIE_MIEJSKO_WIEJSKA = ('3019073', 'Ujście', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                   'pilski', 'powiat')
    WIELKOPOLSKIE_PILSKI_WYRZYSK_MIEJSKO_WIEJSKA = ('3019083', 'Wyrzysk', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                    'pilski', 'powiat')
    WIELKOPOLSKIE_PILSKI_WYSOKA_MIEJSKO_WIEJSKA = ('3019093', 'Wysoka', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                   'pilski', 'powiat')
    WIELKOPOLSKIE_PLESZEWSKI_CHOCZ_MIEJSKO_WIEJSKA = ('3020013', 'Chocz', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'pleszewski', 'powiat')
    WIELKOPOLSKIE_PLESZEWSKI_CZERMIN_WIEJSKA = ('3020022', 'Czermin', GminaType.WIEJSKA, 'wielkopolskie', 'pleszewski',
                                                'powiat')
    WIELKOPOLSKIE_PLESZEWSKI_DOBRZYCA_MIEJSKO_WIEJSKA = ('3020033', 'Dobrzyca', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'pleszewski', 'powiat')
    WIELKOPOLSKIE_PLESZEWSKI_GIZALKI_WIEJSKA = ('3020042', 'Gizałki', GminaType.WIEJSKA, 'wielkopolskie', 'pleszewski',
                                                'powiat')
    WIELKOPOLSKIE_PLESZEWSKI_GOLUCHOW_WIEJSKA = ('3020052', 'Gołuchów', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'pleszewski', 'powiat')
    WIELKOPOLSKIE_PLESZEWSKI_PLESZEW_MIEJSKO_WIEJSKA = ('3020063', 'Pleszew', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'pleszewski', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_LUBON_MIEJSKA = ('3021011', 'Luboń', GminaType.MIEJSKA, 'wielkopolskie', 'poznański',
                                             'powiat')
    WIELKOPOLSKIE_POZNANSKI_PUSZCZYKOWO_MIEJSKA = ('3021021', 'Puszczykowo', GminaType.MIEJSKA, 'wielkopolskie',
                                                   'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_BUK_MIEJSKO_WIEJSKA = ('3021033', 'Buk', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                   'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_CZERWONAK_WIEJSKA = ('3021042', 'Czerwonak', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_DOPIEWO_WIEJSKA = ('3021052', 'Dopiewo', GminaType.WIEJSKA, 'wielkopolskie', 'poznański',
                                               'powiat')
    WIELKOPOLSKIE_POZNANSKI_KLESZCZEWO_WIEJSKA = ('3021062', 'Kleszczewo', GminaType.WIEJSKA, 'wielkopolskie',
                                                  'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_KOMORNIKI_WIEJSKA = ('3021072', 'Komorniki', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_KOSTRZYN_MIEJSKO_WIEJSKA = ('3021083', 'Kostrzyn', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_KORNIK_MIEJSKO_WIEJSKA = ('3021093', 'Kórnik', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_MOSINA_MIEJSKO_WIEJSKA = ('3021103', 'Mosina', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_MUROWANA_GOSLINA_MIEJSKO_WIEJSKA = ('3021113', 'Murowana Goślina',
                                                                GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie', 'poznański',
                                                                'powiat')
    WIELKOPOLSKIE_POZNANSKI_POBIEDZISKA_MIEJSKO_WIEJSKA = ('3021123', 'Pobiedziska', GminaType.MIEJSKO_WIEJSKA,
                                                           'wielkopolskie', 'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_ROKIETNICA_WIEJSKA = ('3021132', 'Rokietnica', GminaType.WIEJSKA, 'wielkopolskie',
                                                  'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_STESZEW_MIEJSKO_WIEJSKA = ('3021143', 'Stęszew', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                       'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_SUCHY_LAS_WIEJSKA = ('3021152', 'Suchy Las', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_SWARZEDZ_MIEJSKO_WIEJSKA = ('3021163', 'Swarzędz', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'poznański', 'powiat')
    WIELKOPOLSKIE_POZNANSKI_TARNOWO_PODGORNE_WIEJSKA = ('3021172', 'Tarnowo Podgórne', GminaType.WIEJSKA,
                                                        'wielkopolskie', 'poznański', 'powiat')
    WIELKOPOLSKIE_RAWICKI_BOJANOWO_MIEJSKO_WIEJSKA = ('3022013', 'Bojanowo', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'rawicki', 'powiat')
    WIELKOPOLSKIE_RAWICKI_JUTROSIN_MIEJSKO_WIEJSKA = ('3022023', 'Jutrosin', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'rawicki', 'powiat')
    WIELKOPOLSKIE_RAWICKI_MIEJSKA_GORKA_MIEJSKO_WIEJSKA = ('3022033', 'Miejska Górka', GminaType.MIEJSKO_WIEJSKA,
                                                           'wielkopolskie', 'rawicki', 'powiat')
    WIELKOPOLSKIE_RAWICKI_PAKOSLAW_WIEJSKA = ('3022042', 'Pakosław', GminaType.WIEJSKA, 'wielkopolskie', 'rawicki',
                                              'powiat')
    WIELKOPOLSKIE_RAWICKI_RAWICZ_MIEJSKO_WIEJSKA = ('3022053', 'Rawicz', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                    'rawicki', 'powiat')
    WIELKOPOLSKIE_SLUPECKI_SLUPCA_MIEJSKA = ('3023011', 'Słupca', GminaType.MIEJSKA, 'wielkopolskie', 'słupecki',
                                             'powiat')
    WIELKOPOLSKIE_SLUPECKI_LADEK_WIEJSKA = ('3023022', 'Lądek', GminaType.WIEJSKA, 'wielkopolskie', 'słupecki',
                                            'powiat')
    WIELKOPOLSKIE_SLUPECKI_ORCHOWO_WIEJSKA = ('3023032', 'Orchowo', GminaType.WIEJSKA, 'wielkopolskie', 'słupecki',
                                              'powiat')
    WIELKOPOLSKIE_SLUPECKI_OSTROWITE_WIEJSKA = ('3023042', 'Ostrowite', GminaType.WIEJSKA, 'wielkopolskie', 'słupecki',
                                                'powiat')
    WIELKOPOLSKIE_SLUPECKI_POWIDZ_WIEJSKA = ('3023052', 'Powidz', GminaType.WIEJSKA, 'wielkopolskie', 'słupecki',
                                             'powiat')
    WIELKOPOLSKIE_SLUPECKI_SLUPCA_WIEJSKA = ('3023062', 'Słupca', GminaType.WIEJSKA, 'wielkopolskie', 'słupecki',
                                             'powiat')
    WIELKOPOLSKIE_SLUPECKI_STRZALKOWO_WIEJSKA = ('3023072', 'Strzałkowo', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'słupecki', 'powiat')
    WIELKOPOLSKIE_SLUPECKI_ZAGOROW_MIEJSKO_WIEJSKA = ('3023083', 'Zagórów', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'słupecki', 'powiat')
    WIELKOPOLSKIE_SZAMOTULSKI_OBRZYCKO_MIEJSKA = ('3024011', 'Obrzycko', GminaType.MIEJSKA, 'wielkopolskie',
                                                  'szamotulski', 'powiat')
    WIELKOPOLSKIE_SZAMOTULSKI_DUSZNIKI_WIEJSKA = ('3024022', 'Duszniki', GminaType.WIEJSKA, 'wielkopolskie',
                                                  'szamotulski', 'powiat')
    WIELKOPOLSKIE_SZAMOTULSKI_KAZMIERZ_WIEJSKA = ('3024032', 'Kaźmierz', GminaType.WIEJSKA, 'wielkopolskie',
                                                  'szamotulski', 'powiat')
    WIELKOPOLSKIE_SZAMOTULSKI_OBRZYCKO_WIEJSKA = ('3024042', 'Obrzycko', GminaType.WIEJSKA, 'wielkopolskie',
                                                  'szamotulski', 'powiat')
    WIELKOPOLSKIE_SZAMOTULSKI_OSTROROG_MIEJSKO_WIEJSKA = ('3024053', 'Ostroróg', GminaType.MIEJSKO_WIEJSKA,
                                                          'wielkopolskie', 'szamotulski', 'powiat')
    WIELKOPOLSKIE_SZAMOTULSKI_PNIEWY_MIEJSKO_WIEJSKA = ('3024063', 'Pniewy', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                        'szamotulski', 'powiat')
    WIELKOPOLSKIE_SZAMOTULSKI_SZAMOTULY_MIEJSKO_WIEJSKA = ('3024073', 'Szamotuły', GminaType.MIEJSKO_WIEJSKA,
                                                           'wielkopolskie', 'szamotulski', 'powiat')
    WIELKOPOLSKIE_SZAMOTULSKI_WRONKI_MIEJSKO_WIEJSKA = ('3024083', 'Wronki', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                        'szamotulski', 'powiat')
    WIELKOPOLSKIE_SREDZKI_DOMINOWO_WIEJSKA = ('3025012', 'Dominowo', GminaType.WIEJSKA, 'wielkopolskie', 'średzki',
                                              'powiat')
    WIELKOPOLSKIE_SREDZKI_KRZYKOSY_WIEJSKA = ('3025022', 'Krzykosy', GminaType.WIEJSKA, 'wielkopolskie', 'średzki',
                                              'powiat')
    WIELKOPOLSKIE_SREDZKI_NOWE_MIASTO_NAD_WARTA_WIEJSKA = ('3025032', 'Nowe Miasto nad Wartą', GminaType.WIEJSKA,
                                                           'wielkopolskie', 'średzki', 'powiat')
    WIELKOPOLSKIE_SREDZKI_SRODA_WIELKOPOLSKA_MIEJSKO_WIEJSKA = ('3025043', 'Środa Wielkopolska',
                                                                GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie', 'średzki',
                                                                'powiat')
    WIELKOPOLSKIE_SREDZKI_ZANIEMYSL_MIEJSKO_WIEJSKA = ('3025053', 'Zaniemyśl', GminaType.MIEJSKO_WIEJSKA,
                                                       'wielkopolskie', 'średzki', 'powiat')
    WIELKOPOLSKIE_SREMSKI_BRODNICA_WIEJSKA = ('3026012', 'Brodnica', GminaType.WIEJSKA, 'wielkopolskie', 'śremski',
                                              'powiat')
    WIELKOPOLSKIE_SREMSKI_DOLSK_MIEJSKO_WIEJSKA = ('3026023', 'Dolsk', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                   'śremski', 'powiat')
    WIELKOPOLSKIE_SREMSKI_KSIAZ_WIELKOPOLSKI_MIEJSKO_WIEJSKA = ('3026033', 'Książ Wielkopolski',
                                                                GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie', 'śremski',
                                                                'powiat')
    WIELKOPOLSKIE_SREMSKI_SREM_MIEJSKO_WIEJSKA = ('3026043', 'Śrem', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                  'śremski', 'powiat')
    WIELKOPOLSKIE_TURECKI_TUREK_MIEJSKA = ('3027011', 'Turek', GminaType.MIEJSKA, 'wielkopolskie', 'turecki', 'powiat')
    WIELKOPOLSKIE_TURECKI_BRUDZEW_WIEJSKA = ('3027022', 'Brudzew', GminaType.WIEJSKA, 'wielkopolskie', 'turecki',
                                             'powiat')
    WIELKOPOLSKIE_TURECKI_DOBRA_MIEJSKO_WIEJSKA = ('3027033', 'Dobra', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                   'turecki', 'powiat')
    WIELKOPOLSKIE_TURECKI_KAWECZYN_WIEJSKA = ('3027042', 'Kawęczyn', GminaType.WIEJSKA, 'wielkopolskie', 'turecki',
                                              'powiat')
    WIELKOPOLSKIE_TURECKI_MALANOW_WIEJSKA = ('3027052', 'Malanów', GminaType.WIEJSKA, 'wielkopolskie', 'turecki',
                                             'powiat')
    WIELKOPOLSKIE_TURECKI_PRZYKONA_WIEJSKA = ('3027062', 'Przykona', GminaType.WIEJSKA, 'wielkopolskie', 'turecki',
                                              'powiat')
    WIELKOPOLSKIE_TURECKI_TULISZKOW_MIEJSKO_WIEJSKA = ('3027073', 'Tuliszków', GminaType.MIEJSKO_WIEJSKA,
                                                       'wielkopolskie', 'turecki', 'powiat')
    WIELKOPOLSKIE_TURECKI_TUREK_WIEJSKA = ('3027082', 'Turek', GminaType.WIEJSKA, 'wielkopolskie', 'turecki', 'powiat')
    WIELKOPOLSKIE_TURECKI_WLADYSLAWOW_WIEJSKA = ('3027092', 'Władysławów', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'turecki', 'powiat')
    WIELKOPOLSKIE_WAGROWIECKI_WAGROWIEC_MIEJSKA = ('3028011', 'Wągrowiec', GminaType.MIEJSKA, 'wielkopolskie',
                                                   'wągrowiecki', 'powiat')
    WIELKOPOLSKIE_WAGROWIECKI_DAMASLAWEK_WIEJSKA = ('3028022', 'Damasławek', GminaType.WIEJSKA, 'wielkopolskie',
                                                    'wągrowiecki', 'powiat')
    WIELKOPOLSKIE_WAGROWIECKI_GOLANCZ_MIEJSKO_WIEJSKA = ('3028033', 'Gołańcz', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'wągrowiecki', 'powiat')
    WIELKOPOLSKIE_WAGROWIECKI_MIESCISKO_MIEJSKO_WIEJSKA = ('3028043', 'Mieścisko', GminaType.MIEJSKO_WIEJSKA,
                                                           'wielkopolskie', 'wągrowiecki', 'powiat')
    WIELKOPOLSKIE_WAGROWIECKI_SKOKI_MIEJSKO_WIEJSKA = ('3028053', 'Skoki', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                       'wągrowiecki', 'powiat')
    WIELKOPOLSKIE_WAGROWIECKI_WAPNO_WIEJSKA = ('3028062', 'Wapno', GminaType.WIEJSKA, 'wielkopolskie', 'wągrowiecki',
                                               'powiat')
    WIELKOPOLSKIE_WAGROWIECKI_WAGROWIEC_WIEJSKA = ('3028072', 'Wągrowiec', GminaType.WIEJSKA, 'wielkopolskie',
                                                   'wągrowiecki', 'powiat')
    WIELKOPOLSKIE_WOLSZTYNSKI_PRZEMET_WIEJSKA = ('3029012', 'Przemęt', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'wolsztyński', 'powiat')
    WIELKOPOLSKIE_WOLSZTYNSKI_SIEDLEC_WIEJSKA = ('3029022', 'Siedlec', GminaType.WIEJSKA, 'wielkopolskie',
                                                 'wolsztyński', 'powiat')
    WIELKOPOLSKIE_WOLSZTYNSKI_WOLSZTYN_MIEJSKO_WIEJSKA = ('3029033', 'Wolsztyn', GminaType.MIEJSKO_WIEJSKA,
                                                          'wielkopolskie', 'wolsztyński', 'powiat')
    WIELKOPOLSKIE_WRZESINSKI_KOLACZKOWO_WIEJSKA = ('3030012', 'Kołaczkowo', GminaType.WIEJSKA, 'wielkopolskie',
                                                   'wrzesiński', 'powiat')
    WIELKOPOLSKIE_WRZESINSKI_MILOSLAW_MIEJSKO_WIEJSKA = ('3030023', 'Miłosław', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'wrzesiński', 'powiat')
    WIELKOPOLSKIE_WRZESINSKI_NEKLA_MIEJSKO_WIEJSKA = ('3030033', 'Nekla', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'wrzesiński', 'powiat')
    WIELKOPOLSKIE_WRZESINSKI_PYZDRY_MIEJSKO_WIEJSKA = ('3030043', 'Pyzdry', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                       'wrzesiński', 'powiat')
    WIELKOPOLSKIE_WRZESINSKI_WRZESNIA_MIEJSKO_WIEJSKA = ('3030053', 'Września', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'wrzesiński', 'powiat')
    WIELKOPOLSKIE_ZLOTOWSKI_ZLOTOW_MIEJSKA = ('3031011', 'Złotów', GminaType.MIEJSKA, 'wielkopolskie', 'złotowski',
                                              'powiat')
    WIELKOPOLSKIE_ZLOTOWSKI_JASTROWIE_MIEJSKO_WIEJSKA = ('3031023', 'Jastrowie', GminaType.MIEJSKO_WIEJSKA,
                                                         'wielkopolskie', 'złotowski', 'powiat')
    WIELKOPOLSKIE_ZLOTOWSKI_KRAJENKA_MIEJSKO_WIEJSKA = ('3031033', 'Krajenka', GminaType.MIEJSKO_WIEJSKA,
                                                        'wielkopolskie', 'złotowski', 'powiat')
    WIELKOPOLSKIE_ZLOTOWSKI_LIPKA_WIEJSKA = ('3031042', 'Lipka', GminaType.WIEJSKA, 'wielkopolskie', 'złotowski',
                                             'powiat')
    WIELKOPOLSKIE_ZLOTOWSKI_OKONEK_MIEJSKO_WIEJSKA = ('3031053', 'Okonek', GminaType.MIEJSKO_WIEJSKA, 'wielkopolskie',
                                                      'złotowski', 'powiat')
    WIELKOPOLSKIE_ZLOTOWSKI_TARNOWKA_WIEJSKA = ('3031062', 'Tarnówka', GminaType.WIEJSKA, 'wielkopolskie', 'złotowski',
                                                'powiat')
    WIELKOPOLSKIE_ZLOTOWSKI_ZAKRZEWO_WIEJSKA = ('3031072', 'Zakrzewo', GminaType.WIEJSKA, 'wielkopolskie', 'złotowski',
                                                'powiat')
    WIELKOPOLSKIE_ZLOTOWSKI_ZLOTOW_WIEJSKA = ('3031082', 'Złotów', GminaType.WIEJSKA, 'wielkopolskie', 'złotowski',
                                              'powiat')
    WIELKOPOLSKIE_KALISZ_KALISZ_MIEJSKA = ('3061011', 'Kalisz', GminaType.MIEJSKA, 'wielkopolskie', 'Kalisz',
                                           'miasto na prawach powiatu')
    WIELKOPOLSKIE_KONIN_KONIN_MIEJSKA = ('3062011', 'Konin', GminaType.MIEJSKA, 'wielkopolskie', 'Konin',
                                         'miasto na prawach powiatu')
    WIELKOPOLSKIE_LESZNO_LESZNO_MIEJSKA = ('3063011', 'Leszno', GminaType.MIEJSKA, 'wielkopolskie', 'Leszno',
                                           'miasto na prawach powiatu')
    WIELKOPOLSKIE_POZNAN_POZNAN_MIEJSKA = ('3064011', 'Poznań', GminaType.MIEJSKA, 'wielkopolskie', 'Poznań',
                                           'miasto na prawach powiatu')

    # Zachodniopomorskie
    ZACHODNIOPOMORSKIE_BIALOGARDZKI_BIALOGARD_MIEJSKA = ('3201011', 'Białogard', GminaType.MIEJSKA,
                                                         'zachodniopomorskie', 'białogardzki', 'powiat')
    ZACHODNIOPOMORSKIE_BIALOGARDZKI_BIALOGARD_WIEJSKA = ('3201022', 'Białogard', GminaType.WIEJSKA,
                                                         'zachodniopomorskie', 'białogardzki', 'powiat')
    ZACHODNIOPOMORSKIE_BIALOGARDZKI_KARLINO_MIEJSKO_WIEJSKA = ('3201033', 'Karlino', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'białogardzki', 'powiat')
    ZACHODNIOPOMORSKIE_BIALOGARDZKI_TYCHOWO_MIEJSKO_WIEJSKA = ('3201043', 'Tychowo', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'białogardzki', 'powiat')
    ZACHODNIOPOMORSKIE_CHOSZCZENSKI_BIERZWNIK_WIEJSKA = ('3202012', 'Bierzwnik', GminaType.WIEJSKA,
                                                         'zachodniopomorskie', 'choszczeński', 'powiat')
    ZACHODNIOPOMORSKIE_CHOSZCZENSKI_CHOSZCZNO_MIEJSKO_WIEJSKA = ('3202023', 'Choszczno', GminaType.MIEJSKO_WIEJSKA,
                                                                 'zachodniopomorskie', 'choszczeński', 'powiat')
    ZACHODNIOPOMORSKIE_CHOSZCZENSKI_DRAWNO_MIEJSKO_WIEJSKA = ('3202033', 'Drawno', GminaType.MIEJSKO_WIEJSKA,
                                                              'zachodniopomorskie', 'choszczeński', 'powiat')
    ZACHODNIOPOMORSKIE_CHOSZCZENSKI_KRZECIN_WIEJSKA = ('3202042', 'Krzęcin', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                       'choszczeński', 'powiat')
    ZACHODNIOPOMORSKIE_CHOSZCZENSKI_PELCZYCE_MIEJSKO_WIEJSKA = ('3202053', 'Pełczyce', GminaType.MIEJSKO_WIEJSKA,
                                                                'zachodniopomorskie', 'choszczeński', 'powiat')
    ZACHODNIOPOMORSKIE_CHOSZCZENSKI_RECZ_MIEJSKO_WIEJSKA = ('3202063', 'Recz', GminaType.MIEJSKO_WIEJSKA,
                                                            'zachodniopomorskie', 'choszczeński', 'powiat')
    ZACHODNIOPOMORSKIE_DRAWSKI_CZAPLINEK_MIEJSKO_WIEJSKA = ('3203013', 'Czaplinek', GminaType.MIEJSKO_WIEJSKA,
                                                            'zachodniopomorskie', 'drawski', 'powiat')
    ZACHODNIOPOMORSKIE_DRAWSKI_DRAWSKO_POMORSKIE_MIEJSKO_WIEJSKA = ('3203023', 'Drawsko Pomorskie',
                                                                    GminaType.MIEJSKO_WIEJSKA, 'zachodniopomorskie',
                                                                    'drawski', 'powiat')
    ZACHODNIOPOMORSKIE_DRAWSKI_KALISZ_POMORSKI_MIEJSKO_WIEJSKA = ('3203033', 'Kalisz Pomorski',
                                                                  GminaType.MIEJSKO_WIEJSKA, 'zachodniopomorskie',
                                                                  'drawski', 'powiat')
    ZACHODNIOPOMORSKIE_DRAWSKI_WIERZCHOWO_WIEJSKA = ('3203052', 'Wierzchowo', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'drawski', 'powiat')
    ZACHODNIOPOMORSKIE_DRAWSKI_ZLOCIENIEC_MIEJSKO_WIEJSKA = ('3203063', 'Złocieniec', GminaType.MIEJSKO_WIEJSKA,
                                                             'zachodniopomorskie', 'drawski', 'powiat')
    ZACHODNIOPOMORSKIE_GOLENIOWSKI_GOLENIOW_MIEJSKO_WIEJSKA = ('3204023', 'Goleniów', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'goleniowski', 'powiat')
    ZACHODNIOPOMORSKIE_GOLENIOWSKI_MASZEWO_MIEJSKO_WIEJSKA = ('3204033', 'Maszewo', GminaType.MIEJSKO_WIEJSKA,
                                                              'zachodniopomorskie', 'goleniowski', 'powiat')
    ZACHODNIOPOMORSKIE_GOLENIOWSKI_NOWOGARD_MIEJSKO_WIEJSKA = ('3204043', 'Nowogard', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'goleniowski', 'powiat')
    ZACHODNIOPOMORSKIE_GOLENIOWSKI_OSINA_WIEJSKA = ('3204052', 'Osina', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                    'goleniowski', 'powiat')
    ZACHODNIOPOMORSKIE_GOLENIOWSKI_PRZYBIERNOW_WIEJSKA = ('3204062', 'Przybiernów', GminaType.WIEJSKA,
                                                          'zachodniopomorskie', 'goleniowski', 'powiat')
    ZACHODNIOPOMORSKIE_GOLENIOWSKI_STEPNICA_MIEJSKO_WIEJSKA = ('3204073', 'Stepnica', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'goleniowski', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFICKI_BROJCE_WIEJSKA = ('3205012', 'Brojce', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                  'gryficki', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFICKI_GRYFICE_MIEJSKO_WIEJSKA = ('3205023', 'Gryfice', GminaType.MIEJSKO_WIEJSKA,
                                                           'zachodniopomorskie', 'gryficki', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFICKI_KARNICE_WIEJSKA = ('3205032', 'Karnice', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                   'gryficki', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFICKI_PLOTY_MIEJSKO_WIEJSKA = ('3205043', 'Płoty', GminaType.MIEJSKO_WIEJSKA,
                                                         'zachodniopomorskie', 'gryficki', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFICKI_REWAL_WIEJSKA = ('3205072', 'Rewal', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                 'gryficki', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFICKI_TRZEBIATOW_MIEJSKO_WIEJSKA = ('3205083', 'Trzebiatów', GminaType.MIEJSKO_WIEJSKA,
                                                              'zachodniopomorskie', 'gryficki', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFINSKI_BANIE_WIEJSKA = ('3206012', 'Banie', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                  'gryfiński', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFINSKI_CEDYNIA_MIEJSKO_WIEJSKA = ('3206023', 'Cedynia', GminaType.MIEJSKO_WIEJSKA,
                                                            'zachodniopomorskie', 'gryfiński', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFINSKI_CHOJNA_MIEJSKO_WIEJSKA = ('3206033', 'Chojna', GminaType.MIEJSKO_WIEJSKA,
                                                           'zachodniopomorskie', 'gryfiński', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFINSKI_GRYFINO_MIEJSKO_WIEJSKA = ('3206043', 'Gryfino', GminaType.MIEJSKO_WIEJSKA,
                                                            'zachodniopomorskie', 'gryfiński', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFINSKI_MIESZKOWICE_MIEJSKO_WIEJSKA = ('3206053', 'Mieszkowice', GminaType.MIEJSKO_WIEJSKA,
                                                                'zachodniopomorskie', 'gryfiński', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFINSKI_MORYN_MIEJSKO_WIEJSKA = ('3206063', 'Moryń', GminaType.MIEJSKO_WIEJSKA,
                                                          'zachodniopomorskie', 'gryfiński', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFINSKI_STARE_CZARNOWO_WIEJSKA = ('3206072', 'Stare Czarnowo', GminaType.WIEJSKA,
                                                           'zachodniopomorskie', 'gryfiński', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFINSKI_TRZCINSKO_ZDROJ_MIEJSKO_WIEJSKA = ('3206083', 'Trzcińsko-Zdrój',
                                                                    GminaType.MIEJSKO_WIEJSKA, 'zachodniopomorskie',
                                                                    'gryfiński', 'powiat')
    ZACHODNIOPOMORSKIE_GRYFINSKI_WIDUCHOWA_WIEJSKA = ('3206092', 'Widuchowa', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                      'gryfiński', 'powiat')
    ZACHODNIOPOMORSKIE_KAMIENSKI_DZIWNOW_MIEJSKO_WIEJSKA = ('3207013', 'Dziwnów', GminaType.MIEJSKO_WIEJSKA,
                                                            'zachodniopomorskie', 'kamieński', 'powiat')
    ZACHODNIOPOMORSKIE_KAMIENSKI_GOLCZEWO_MIEJSKO_WIEJSKA = ('3207023', 'Golczewo', GminaType.MIEJSKO_WIEJSKA,
                                                             'zachodniopomorskie', 'kamieński', 'powiat')
    ZACHODNIOPOMORSKIE_KAMIENSKI_KAMIEN_POMORSKI_MIEJSKO_WIEJSKA = ('3207033', 'Kamień Pomorski',
                                                                    GminaType.MIEJSKO_WIEJSKA, 'zachodniopomorskie',
                                                                    'kamieński', 'powiat')
    ZACHODNIOPOMORSKIE_KAMIENSKI_MIEDZYZDROJE_MIEJSKO_WIEJSKA = ('3207043', 'Międzyzdroje', GminaType.MIEJSKO_WIEJSKA,
                                                                 'zachodniopomorskie', 'kamieński', 'powiat')
    ZACHODNIOPOMORSKIE_KAMIENSKI_SWIERZNO_WIEJSKA = ('3207052', 'Świerzno', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'kamieński', 'powiat')
    ZACHODNIOPOMORSKIE_KAMIENSKI_WOLIN_MIEJSKO_WIEJSKA = ('3207063', 'Wolin', GminaType.MIEJSKO_WIEJSKA,
                                                          'zachodniopomorskie', 'kamieński', 'powiat')
    ZACHODNIOPOMORSKIE_KOLOBRZESKI_KOLOBRZEG_MIEJSKA = ('3208011', 'Kołobrzeg', GminaType.MIEJSKA, 'zachodniopomorskie',
                                                        'kołobrzeski', 'powiat')
    ZACHODNIOPOMORSKIE_KOLOBRZESKI_DYGOWO_WIEJSKA = ('3208022', 'Dygowo', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'kołobrzeski', 'powiat')
    ZACHODNIOPOMORSKIE_KOLOBRZESKI_GOSCINO_MIEJSKO_WIEJSKA = ('3208033', 'Gościno', GminaType.MIEJSKO_WIEJSKA,
                                                              'zachodniopomorskie', 'kołobrzeski', 'powiat')
    ZACHODNIOPOMORSKIE_KOLOBRZESKI_KOLOBRZEG_WIEJSKA = ('3208042', 'Kołobrzeg', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                        'kołobrzeski', 'powiat')
    ZACHODNIOPOMORSKIE_KOLOBRZESKI_RYMAN_WIEJSKA = ('3208052', 'Rymań', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                    'kołobrzeski', 'powiat')
    ZACHODNIOPOMORSKIE_KOLOBRZESKI_SIEMYSL_WIEJSKA = ('3208062', 'Siemyśl', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                      'kołobrzeski', 'powiat')
    ZACHODNIOPOMORSKIE_KOLOBRZESKI_USTRONIE_MORSKIE_WIEJSKA = ('3208072', 'Ustronie Morskie', GminaType.WIEJSKA,
                                                               'zachodniopomorskie', 'kołobrzeski', 'powiat')
    ZACHODNIOPOMORSKIE_KOSZALINSKI_BEDZINO_WIEJSKA = ('3209012', 'Będzino', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                      'koszaliński', 'powiat')
    ZACHODNIOPOMORSKIE_KOSZALINSKI_BIESIEKIERZ_WIEJSKA = ('3209022', 'Biesiekierz', GminaType.WIEJSKA,
                                                          'zachodniopomorskie', 'koszaliński', 'powiat')
    ZACHODNIOPOMORSKIE_KOSZALINSKI_BOBOLICE_MIEJSKO_WIEJSKA = ('3209033', 'Bobolice', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'koszaliński', 'powiat')
    ZACHODNIOPOMORSKIE_KOSZALINSKI_MANOWO_WIEJSKA = ('3209042', 'Manowo', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'koszaliński', 'powiat')
    ZACHODNIOPOMORSKIE_KOSZALINSKI_MIELNO_MIEJSKO_WIEJSKA = ('3209053', 'Mielno', GminaType.MIEJSKO_WIEJSKA,
                                                             'zachodniopomorskie', 'koszaliński', 'powiat')
    ZACHODNIOPOMORSKIE_KOSZALINSKI_POLANOW_MIEJSKO_WIEJSKA = ('3209063', 'Polanów', GminaType.MIEJSKO_WIEJSKA,
                                                              'zachodniopomorskie', 'koszaliński', 'powiat')
    ZACHODNIOPOMORSKIE_KOSZALINSKI_SIANOW_MIEJSKO_WIEJSKA = ('3209073', 'Sianów', GminaType.MIEJSKO_WIEJSKA,
                                                             'zachodniopomorskie', 'koszaliński', 'powiat')
    ZACHODNIOPOMORSKIE_KOSZALINSKI_SWIESZYNO_WIEJSKA = ('3209082', 'Świeszyno', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                        'koszaliński', 'powiat')
    ZACHODNIOPOMORSKIE_MYSLIBORSKI_BARLINEK_MIEJSKO_WIEJSKA = ('3210013', 'Barlinek', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'myśliborski', 'powiat')
    ZACHODNIOPOMORSKIE_MYSLIBORSKI_BOLESZKOWICE_WIEJSKA = ('3210022', 'Boleszkowice', GminaType.WIEJSKA,
                                                           'zachodniopomorskie', 'myśliborski', 'powiat')
    ZACHODNIOPOMORSKIE_MYSLIBORSKI_DEBNO_MIEJSKO_WIEJSKA = ('3210033', 'Dębno', GminaType.MIEJSKO_WIEJSKA,
                                                            'zachodniopomorskie', 'myśliborski', 'powiat')
    ZACHODNIOPOMORSKIE_MYSLIBORSKI_MYSLIBORZ_MIEJSKO_WIEJSKA = ('3210043', 'Myślibórz', GminaType.MIEJSKO_WIEJSKA,
                                                                'zachodniopomorskie', 'myśliborski', 'powiat')
    ZACHODNIOPOMORSKIE_MYSLIBORSKI_NOWOGRODEK_POMORSKI_WIEJSKA = ('3210052', 'Nowogródek Pomorski', GminaType.WIEJSKA,
                                                                  'zachodniopomorskie', 'myśliborski', 'powiat')
    ZACHODNIOPOMORSKIE_POLICKI_DOBRA_SZCZECINSKA_WIEJSKA = ('3211012', 'Dobra (Szczecińska)', GminaType.WIEJSKA,
                                                            'zachodniopomorskie', 'policki', 'powiat')
    ZACHODNIOPOMORSKIE_POLICKI_KOLBASKOWO_WIEJSKA = ('3211022', 'Kołbaskowo', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'policki', 'powiat')
    ZACHODNIOPOMORSKIE_POLICKI_NOWE_WARPNO_MIEJSKO_WIEJSKA = ('3211033', 'Nowe Warpno', GminaType.MIEJSKO_WIEJSKA,
                                                              'zachodniopomorskie', 'policki', 'powiat')
    ZACHODNIOPOMORSKIE_POLICKI_POLICE_MIEJSKO_WIEJSKA = ('3211043', 'Police', GminaType.MIEJSKO_WIEJSKA,
                                                         'zachodniopomorskie', 'policki', 'powiat')
    ZACHODNIOPOMORSKIE_PYRZYCKI_BIELICE_WIEJSKA = ('3212012', 'Bielice', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                   'pyrzycki', 'powiat')
    ZACHODNIOPOMORSKIE_PYRZYCKI_KOZIELICE_WIEJSKA = ('3212022', 'Kozielice', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'pyrzycki', 'powiat')
    ZACHODNIOPOMORSKIE_PYRZYCKI_LIPIANY_MIEJSKO_WIEJSKA = ('3212033', 'Lipiany', GminaType.MIEJSKO_WIEJSKA,
                                                           'zachodniopomorskie', 'pyrzycki', 'powiat')
    ZACHODNIOPOMORSKIE_PYRZYCKI_PRZELEWICE_WIEJSKA = ('3212042', 'Przelewice', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                      'pyrzycki', 'powiat')
    ZACHODNIOPOMORSKIE_PYRZYCKI_PYRZYCE_MIEJSKO_WIEJSKA = ('3212053', 'Pyrzyce', GminaType.MIEJSKO_WIEJSKA,
                                                           'zachodniopomorskie', 'pyrzycki', 'powiat')
    ZACHODNIOPOMORSKIE_PYRZYCKI_WARNICE_WIEJSKA = ('3212062', 'Warnice', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                   'pyrzycki', 'powiat')
    ZACHODNIOPOMORSKIE_SLAWIENSKI_DARLOWO_MIEJSKA = ('3213011', 'Darłowo', GminaType.MIEJSKA, 'zachodniopomorskie',
                                                     'sławieński', 'powiat')
    ZACHODNIOPOMORSKIE_SLAWIENSKI_SLAWNO_MIEJSKA = ('3213021', 'Sławno', GminaType.MIEJSKA, 'zachodniopomorskie',
                                                    'sławieński', 'powiat')
    ZACHODNIOPOMORSKIE_SLAWIENSKI_DARLOWO_WIEJSKA = ('3213032', 'Darłowo', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'sławieński', 'powiat')
    ZACHODNIOPOMORSKIE_SLAWIENSKI_MALECHOWO_WIEJSKA = ('3213042', 'Malechowo', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                       'sławieński', 'powiat')
    ZACHODNIOPOMORSKIE_SLAWIENSKI_POSTOMINO_WIEJSKA = ('3213052', 'Postomino', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                       'sławieński', 'powiat')
    ZACHODNIOPOMORSKIE_SLAWIENSKI_SLAWNO_WIEJSKA = ('3213062', 'Sławno', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                    'sławieński', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_STARGARD_MIEJSKA = ('3214011', 'Stargard', GminaType.MIEJSKA, 'zachodniopomorskie',
                                                       'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_CHOCIWEL_MIEJSKO_WIEJSKA = ('3214023', 'Chociwel', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_DOBRZANY_MIEJSKO_WIEJSKA = ('3214033', 'Dobrzany', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_DOLICE_WIEJSKA = ('3214042', 'Dolice', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_INSKO_MIEJSKO_WIEJSKA = ('3214053', 'Ińsko', GminaType.MIEJSKO_WIEJSKA,
                                                            'zachodniopomorskie', 'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_KOBYLANKA_WIEJSKA = ('3214062', 'Kobylanka', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                        'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_MARIANOWO_WIEJSKA = ('3214082', 'Marianowo', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                        'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_STARA_DABROWA_WIEJSKA = ('3214092', 'Stara Dąbrowa', GminaType.WIEJSKA,
                                                            'zachodniopomorskie', 'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_STARGARD_WIEJSKA = ('3214102', 'Stargard', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                       'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_STARGARDZKI_SUCHAN_MIEJSKO_WIEJSKA = ('3214113', 'Suchań', GminaType.MIEJSKO_WIEJSKA,
                                                             'zachodniopomorskie', 'stargardzki', 'powiat')
    ZACHODNIOPOMORSKIE_SZCZECINECKI_SZCZECINEK_MIEJSKA = ('3215011', 'Szczecinek', GminaType.MIEJSKA,
                                                          'zachodniopomorskie', 'szczecinecki', 'powiat')
    ZACHODNIOPOMORSKIE_SZCZECINECKI_BARWICE_MIEJSKO_WIEJSKA = ('3215023', 'Barwice', GminaType.MIEJSKO_WIEJSKA,
                                                               'zachodniopomorskie', 'szczecinecki', 'powiat')
    ZACHODNIOPOMORSKIE_SZCZECINECKI_BIALY_BOR_MIEJSKO_WIEJSKA = ('3215033', 'Biały Bór', GminaType.MIEJSKO_WIEJSKA,
                                                                 'zachodniopomorskie', 'szczecinecki', 'powiat')
    ZACHODNIOPOMORSKIE_SZCZECINECKI_BORNE_SULINOWO_MIEJSKO_WIEJSKA = ('3215043', 'Borne Sulinowo',
                                                                      GminaType.MIEJSKO_WIEJSKA, 'zachodniopomorskie',
                                                                      'szczecinecki', 'powiat')
    ZACHODNIOPOMORSKIE_SZCZECINECKI_GRZMIACA_WIEJSKA = ('3215052', 'Grzmiąca', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                        'szczecinecki', 'powiat')
    ZACHODNIOPOMORSKIE_SZCZECINECKI_SZCZECINEK_WIEJSKA = ('3215062', 'Szczecinek', GminaType.WIEJSKA,
                                                          'zachodniopomorskie', 'szczecinecki', 'powiat')
    ZACHODNIOPOMORSKIE_SWIDWINSKI_SWIDWIN_MIEJSKA = ('3216011', 'Świdwin', GminaType.MIEJSKA, 'zachodniopomorskie',
                                                     'świdwiński', 'powiat')
    ZACHODNIOPOMORSKIE_SWIDWINSKI_BRZEZNO_WIEJSKA = ('3216022', 'Brzeżno', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'świdwiński', 'powiat')
    ZACHODNIOPOMORSKIE_SWIDWINSKI_POLCZYN_ZDROJ_MIEJSKO_WIEJSKA = ('3216033', 'Połczyn-Zdrój',
                                                                   GminaType.MIEJSKO_WIEJSKA, 'zachodniopomorskie',
                                                                   'świdwiński', 'powiat')
    ZACHODNIOPOMORSKIE_SWIDWINSKI_RABINO_WIEJSKA = ('3216042', 'Rąbino', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                    'świdwiński', 'powiat')
    ZACHODNIOPOMORSKIE_SWIDWINSKI_SLAWOBORZE_WIEJSKA = ('3216052', 'Sławoborze', GminaType.WIEJSKA,
                                                        'zachodniopomorskie', 'świdwiński', 'powiat')
    ZACHODNIOPOMORSKIE_SWIDWINSKI_SWIDWIN_WIEJSKA = ('3216062', 'Świdwin', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                     'świdwiński', 'powiat')
    ZACHODNIOPOMORSKIE_WALECKI_WALCZ_MIEJSKA = ('3217011', 'Wałcz', GminaType.MIEJSKA, 'zachodniopomorskie', 'wałecki',
                                                'powiat')
    ZACHODNIOPOMORSKIE_WALECKI_CZLOPA_MIEJSKO_WIEJSKA = ('3217023', 'Człopa', GminaType.MIEJSKO_WIEJSKA,
                                                         'zachodniopomorskie', 'wałecki', 'powiat')
    ZACHODNIOPOMORSKIE_WALECKI_MIROSLAWIEC_MIEJSKO_WIEJSKA = ('3217033', 'Mirosławiec', GminaType.MIEJSKO_WIEJSKA,
                                                              'zachodniopomorskie', 'wałecki', 'powiat')
    ZACHODNIOPOMORSKIE_WALECKI_TUCZNO_MIEJSKO_WIEJSKA = ('3217043', 'Tuczno', GminaType.MIEJSKO_WIEJSKA,
                                                         'zachodniopomorskie', 'wałecki', 'powiat')
    ZACHODNIOPOMORSKIE_WALECKI_WALCZ_WIEJSKA = ('3217052', 'Wałcz', GminaType.WIEJSKA, 'zachodniopomorskie', 'wałecki',
                                                'powiat')
    ZACHODNIOPOMORSKIE_LOBESKI_DOBRA_MIEJSKO_WIEJSKA = ('3218013', 'Dobra', GminaType.MIEJSKO_WIEJSKA,
                                                        'zachodniopomorskie', 'łobeski', 'powiat')
    ZACHODNIOPOMORSKIE_LOBESKI_LOBEZ_MIEJSKO_WIEJSKA = ('3218023', 'Łobez', GminaType.MIEJSKO_WIEJSKA,
                                                        'zachodniopomorskie', 'łobeski', 'powiat')
    ZACHODNIOPOMORSKIE_LOBESKI_RADOWO_MALE_WIEJSKA = ('3218032', 'Radowo Małe', GminaType.WIEJSKA, 'zachodniopomorskie',
                                                      'łobeski', 'powiat')
    ZACHODNIOPOMORSKIE_LOBESKI_RESKO_MIEJSKO_WIEJSKA = ('3218043', 'Resko', GminaType.MIEJSKO_WIEJSKA,
                                                        'zachodniopomorskie', 'łobeski', 'powiat')
    ZACHODNIOPOMORSKIE_LOBESKI_WEGORZYNO_MIEJSKO_WIEJSKA = ('3218053', 'Węgorzyno', GminaType.MIEJSKO_WIEJSKA,
                                                            'zachodniopomorskie', 'łobeski', 'powiat')
    ZACHODNIOPOMORSKIE_KOSZALIN_KOSZALIN_MIEJSKA = ('3261011', 'Koszalin', GminaType.MIEJSKA, 'zachodniopomorskie',
                                                    'Koszalin', 'miasto na prawach powiatu')
    ZACHODNIOPOMORSKIE_SZCZECIN_SZCZECIN_MIEJSKA = ('3262011', 'Szczecin', GminaType.MIEJSKA, 'zachodniopomorskie',
                                                    'Szczecin', 'miasto na prawach powiatu')
    ZACHODNIOPOMORSKIE_SWINOUJSCIE_SWINOUJSCIE_MIEJSKA = ('3263011', 'Świnoujście', GminaType.MIEJSKA,
                                                          'zachodniopomorskie', 'Świnoujście',
                                                          'miasto na prawach powiatu')

    def __new__(
            cls,
            teryt: str,
            label: str,
            gmina_type: GminaType,
            wojewodztwo: str,
            powiat: str,
            powiat_kind: str,
    ) -> Gmina:
        obj = object.__new__(cls)
        obj._value_ = teryt
        obj.label = label
        obj.gmina_type = gmina_type
        obj.wojewodztwo = wojewodztwo
        obj.powiat = powiat
        obj.powiat_kind = powiat_kind
        return obj

    @property
    def teryt(self) -> tuple[str, str, GminaType, str, str, str]:
        return self.value

    @property
    def display_name(self) -> str:
        return f"{self.gmina_type.value} {self.label}"

    @property
    def is_city_county(self) -> bool:
        return self.powiat_kind == "miasto na prawach powiatu"

    @classmethod
    def from_teryt(cls, teryt: str) -> Gmina:
        """Zwraca gminę na podstawie siedmiocyfrowego kodu TERYT."""
        normalized = str(teryt).strip()
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"Nieznany kod TERYT gminy: {teryt!r}") from exc

    @classmethod
    def for_wojewodztwo(cls, wojewodztwo: str) -> list[Gmina]:
        """Zwraca wszystkie gminy danego województwa."""
        normalized = wojewodztwo.strip().casefold()
        return [gmina for gmina in cls if gmina.wojewodztwo.casefold() == normalized]

    @classmethod
    def for_powiat(
            cls,
            powiat: str,
            *,
            wojewodztwo: str | None = None,
    ) -> list[Gmina]:
        """Zwraca gminy powiatu; województwo rozstrzyga powtarzalne nazwy."""
        normalized_powiat = powiat.strip().casefold()
        normalized_woj = wojewodztwo.strip().casefold() if wojewodztwo else None
        return [
            gmina
            for gmina in cls
            if gmina.powiat.casefold() == normalized_powiat
               and (normalized_woj is None or gmina.wojewodztwo.casefold() == normalized_woj)
        ]

    def __str__(self) -> str:
        return self.label
