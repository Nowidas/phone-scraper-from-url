import sys

import requests
from lxml import html
from urllib.parse import urljoin, urlparse

import phonenumbers
from collections import Counter


def validate_page_links(site, page_links, internal_links):
    """search for internal links, and returns unique links"""
    new_found_links = []
    for link in page_links:
        link = link.attrib["href"]
        if "/" in link and "#" in link.split("/")[-1]:
            continue
        if (
            link.startswith("/")
            and len(link) > 1
            and not link.endswith(".pdf")
            and link not in internal_links
            and link not in new_found_links
        ):
            new_found_links.append(link)
        elif (
            link.startswith(site)
            and len(link) > 1
            and not link.endswith(".pdf")
            and link.replace(site, "") not in internal_links
            and link.replace(site, "") not in new_found_links
        ):
            new_found_links.append(link.replace(site, ""))
        elif (
            link.startswith(site.replace("www.", ""))
            and len(link) > 1
            and not link.endswith(".pdf")
            and link.replace(site.replace("www.", ""), "") not in internal_links
            and link.replace(site.replace("www.", ""), "") not in new_found_links
        ):
            new_found_links.append(link.replace(site, ""))
    return new_found_links


def prioritize_page_links(internal_links):
    """search only given list of pages and returns filterd internal_links"""
    internal_links = [
        link
        for link in internal_links
        if sum(
            [
                text in link.lower()
                for text in [
                    "/kontakt",
                    "datenschutz",
                    "polityka-prywatnosci",
                    "contact",
                    "regulamin",
                ]
            ]
        )
    ]
    return internal_links


def guesse_country_code(site):
    """returns code name for phone parsing from site domain"""
    if ".pl" in site:
        return "PL"
    elif ".de" in site:
        return "DE"
    # elif '.com' in site:
    #     return 'US'
    else:
        return None


def scrape(site: str) -> str:
    site = urlparse(site)
    try:
        main_page = requests.get(site.geturl())
    except:
        # print('❌ conn error\n')
        return "connection error"
    # change main site if redericted
    site = urlparse(
        "{url.scheme}://{www}{url.netloc}/".format(
            url=urlparse(main_page.url), www="www." if "www." in site else ""
        )
    )

    main_tree = html.fromstring(main_page.content)
    page_links = main_tree.xpath("//a[@href]")

    internal_links = validate_page_links(site.geturl(), page_links, [""])
    internal_links = [""] + prioritize_page_links(internal_links)

    it = -1
    found_phone_numbers = []
    for link in internal_links:
        it += 1
        # print(it+1, '/', len(internal_links), '. ', urljoin(site.geturl(), link))

        page = requests.get(urljoin(site.geturl(), link))
        tree = html.fromstring(page.content)
        page_links = tree.xpath("//a[@href]")
        page_text = tree.xpath("//*[not(self::script)]/text()")

        internal_links.extend(
            prioritize_page_links(
                validate_page_links(site.geturl(), page_links, internal_links)
            )
        )
        # found_phone_links = [p_link.attrib['href'].replace('tel:', '') for p_link in page_links if p_link.attrib['href'].startswith('tel:')]

        return_next_num = False
        # for every text element on page
        for text in page_text:
            text = text.strip()
            # Calculate Assumption 2 (If number after clue_word -> must me main number)
            if sum(
                [
                    clue_word in text.lower()
                    for clue_word in [
                        "zentrale",
                        "infolinia",
                        "centrala",
                        "headquarters",
                    ]
                ]
            ):
                # print('⚠️ NEXT could BE DE ZENTRALE ⚠️')
                return_next_num = True
            # for every phone found in text element
            for match in phonenumbers.PhoneNumberMatcher(
                text, guesse_country_code(site.geturl())
            ):
                # Not count if number after given words (ex. fax):
                if sum([clue_word in text.lower() for clue_word in ["fax"]]):
                    break
                # Phone to one uniformed format
                string_phone_parsed = phonenumbers.format_number(
                    match.number, phonenumbers.PhoneNumberFormat.E164
                )
                # dont accept short numbers (often mistaken with wrong date format: 22.6.2022)
                if len(string_phone_parsed) <= 9:
                    continue
                # Assumption 1: If number on main page -> must me main number
                if it == 0:
                    # print('end(✅) ', string_phone_parsed, '\n')
                    return string_phone_parsed
                # Assumption 2: If number after clue_word -> must me main number
                if return_next_num:
                    # print('end(✅) ', string_phone_parsed, '\n')
                    return string_phone_parsed
                # print('append📞', string_phone_parsed)
                found_phone_numbers.append(string_phone_parsed)
    # Assumption 3: If number most used on site -> must me main number (else return first found)
    if most_common := Counter(found_phone_numbers).most_common(1):
        # print('end(✅) ', most_common[0][0], '\n')
        return most_common[0][0]
    else:
        # print('end(❌) \n')
        return ""


# tested on:
# scrape('https://www.orlen.pl')  # (24) 256 00 00  ✅
# scrape('https://www.zabka.pl/')  # tel: 61 856 37 00 ✅
# scrape('https://www.lindt.de/')  # +498008088400 ✅
# scrape('https://www.pumox.com/')  # +49 561 473 953 30 ✅
# scrape('https://www.nestle.de/')  # +49 6966710 ✅
# scrape('http://www.lactalis.de/home.html')  # +49 7851 94380  ✅
# scrape('http://www.hellma.de')  # +49 911 934480 ✅
# scrape('http://www.zum-dorfkrug.de/')  # +49 40 3006990 ✅
# scrape('https://www.prolupin.de/')  # +49 (0) 38326 5383 11  ✅ ❗>(http a https diff)<❗
# scrape('https://www.froneri.de/')  # 0911-938-0 ✅
# scrape('https://pl.asseco.com/')  # +48 17 888 55 55 ✅
# scrape('http://milupa-nutricia.de/')  # +49 69 7191350 ❗site didnt work when tested
# scrape('https://www.riemerschmid.de/')  # +498122411139 ✅
# scrape('https://zeb-consulting.com/')  # +49251971280 ✅
# scrape('http://www.kattus.de/')  # +49 5421 3090 ✅
# scrape('http://www.bahlsen.de/')  # +49 511 9600
# scrape('https://www.mondelezinternational.com/')  # +18479434000 ✅
# scrape('https://www.lorenz-snackworld.de/')  # +4961022930 ✅
# scrape('https://dreistern-gerichte.de/')  # +49 3391 59570 ✅
# scrape('https://www.dreistern-genuss.de/')  # +49 3391 59570 ✅
# scrape('http://www.zhg-online.de/')  # +49781616245 ✅
# scrape('http://www.lieken.de/')  # +494474891585 ✅
# scrape('http://www.oetker.de/')  # 00800 - 71 72 73 74 ✅
# scrape('https://www.ruf.eu/')  # +49 5431 1850 ✅
# scrape('http://www.griesson-debeukelaer.de/')  # +49 2654 4010 ✅
# scrape('http://www.unilever.de/')  # +4940696392555 ✅
# scrape('https://www.iglo.de/')  # +49 40180 249 0 ✅


if len(sys.argv) > 1:
    print(scrape(sys.argv[1]))
else:
    print("Missing <web-site-url> argument")
