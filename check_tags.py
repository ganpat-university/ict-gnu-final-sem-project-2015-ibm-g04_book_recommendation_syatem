import pandas as pd

tags_df = pd.read_csv('data/tags.csv')

our_tags = [
    'fiction', 'fantasy', 'magic', 'urban-fantasy', 'science-fiction', 'sci-fi', 
    'mystery', 'crime', 'detective', 'true-crime', 'thriller', 'suspense', 
    'romance', 'chick-lit', 'paranormal-romance', 'historical-fiction', 'historical',
    'non-fiction', 'nonfiction', 'young-adult', 'ya', 'new-adult', 
    'classics', 'classic', 'literature', 'horror', 'vampires', 'paranormal', 'supernatural',
    'dystopian', 'dystopia', 'contemporary', 'adult-fiction', 'adventure', 
    'western', 'cowboys', 'childrens', 'children', 'children-s', 'middle-grade',
    'graphic-novels', 'comics', 'manga', 'memoir', 'autobiography', 
    'biography', 'biographies', 'history', 'self-help', 'personal-development',
    'psychology', 'science', 'philosophy', 'religion', 'spirituality', 'christian',
    'business', 'economics', 'travel', 'cookbooks', 'food', 'cooking',
    'art', 'photography', 'humor', 'comedy', 'satire', 'poetry', 
    'short-stories', 'essays', 'drama', 'plays', 'fairy-tales', 'folklore', 'mythology',
    'lgbt', 'lgbtq', 'queer', 'politics', 'political'
]

found = []
not_found = []
all_tags_lower = tags_df['tag_name'].str.lower().tolist()

for tag in our_tags:
    if tag in all_tags_lower:
        found.append(tag)
    else:
        not_found.append(tag)

print(f'FOUND in dataset: {len(found)}/{len(our_tags)}')
print(f'\nMISSING tags ({len(not_found)}):')
for tag in not_found:
    print(f'  ❌ {tag}')

print(f'\nFOUND tags ({len(found)}):')
for tag in found[:30]:
    print(f'  ✓ {tag}')
if len(found) > 30:
    print(f'  ... and {len(found)-30} more')
