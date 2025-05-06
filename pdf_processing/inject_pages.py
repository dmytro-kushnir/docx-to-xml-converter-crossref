def inject_pages_into_articles(articles_data, pages_data):
    if len(articles_data) != len(pages_data):
        raise ValueError(f"Кількість статей ({len(articles_data)}) не збігається з кількістю записів сторінок у PDF ({len(pages_data)})")

    updated_articles = []
    for i, article in enumerate(articles_data):
        old_range = article[3]
        new_range = (pages_data[i]["start_page"], pages_data[i]["end_page"])
        updated = (
            article[0],  # english_title
            article[1],  # ukrainian_title
            article[2],  # authors
            new_range,
            article[4],  # references
            article[5],  # abstract
        )
        print(f"[INFO] '{article[0]}': сторінки змінено з {old_range} на {new_range}")
        updated_articles.append(updated)

    return updated_articles

