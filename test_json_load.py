import pandas as pd
import json
from pathlib import Path

data_dir = Path('data')
file_path = data_dir / 'testing_of_goodreads.json'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# The JSON file has concatenated objects like }\n{
content = '[' + content.replace('}\n{', '},\n{') + ']'
data = json.loads(content)
df = pd.DataFrame(data)

try:
    old_books = pd.read_csv(data_dir / 'books.csv', usecols=['book_id', 'goodreads_book_id'])
    # Mapping from str(goodreads_id) -> book_id
    mapping = dict(zip(old_books['goodreads_book_id'].dropna().astype(int).astype(str), old_books['book_id']))
except Exception as e:
    print("No mapping", e)
    mapping = {}

df['goodreads_book_id'] = pd.to_numeric(df['book_id'], errors='coerce')

new_id_start = 100000
def assign_id(gr_id):
    global new_id_start
    str_id = str(int(gr_id)) if pd.notna(gr_id) else ""
    if str_id in mapping:
        return mapping[str_id]
    new_id_start += 1
    return new_id_start

df['book_id'] = df['goodreads_book_id'].apply(assign_id).astype(int)

df = df.rename(columns={
    'average_rating': 'avg_rating',
    'ratings_count': 'rating_count',
    'image_url': 'image_url_m',
    'publication_year': 'year',
    'title_without_series': 'original_title',
    'language_code': 'language'
})

if 'image_url_m' in df.columns:
    df['image_url_l'] = df['image_url_m']
    df['image_url_s'] = df['image_url_m']

if 'year' in df.columns:
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df['year'] = df['year'].fillna(0).astype(int)

def extract_author(authors_list):
    if isinstance(authors_list, list) and len(authors_list) > 0:
        author_id = authors_list[0].get('author_id', '')
        return f"Author {author_id}" if author_id else "Unknown Author"
    return "Unknown Author"

if 'authors' in df.columns:
    df['author'] = df['authors'].apply(extract_author)
else:
    df['author'] = 'Unknown Author'

if 'original_title' not in df.columns:
    df['original_title'] = df['title']
df['title'] = df['title'].fillna(df['original_title']).fillna('Unknown Title')

df['rating_count'] = pd.to_numeric(df['rating_count'], errors='coerce').fillna(0).astype(int)
df['avg_rating'] = pd.to_numeric(df['avg_rating'], errors='coerce').fillna(0.0).astype(float)

print(df[['book_id', 'goodreads_book_id', 'title', 'author', 'year']].head())
print("Total rows:", len(df))
print("Overlapped ratings book_id mapped:", df[df['book_id'] < 10000]['book_id'].tolist())
