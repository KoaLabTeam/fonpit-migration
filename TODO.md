### import strategy

- slow import
  - download all relevant csv files
  - create items in order
    - authors
      - mark inactive authors somehow (email-address & status)
    - categories
    - tags
    - featureimages / all media files?
      - create meta-field/custom field with original ID and original URL
  - create articles
    - add meta-field/custom field with original ID and original URL
    - add all relevant meta-fields
  - second pass on articles
    - correct internal links with new articles/pages
    - correct internal image references with new ones
  - make it resilient - write errors into separate-files for later retry


- sync
  - get changes of the mysql database
  - update/insert changes for
    - authors
    - categories
    - tags
    - media files
    - articles
    
  
    



- upsert for everything (try clever hashing to find duplicates?)
- in order to maintain relationships:
  - authors
  - users(? corresponding to community plugin?)
  - terms & taxonomy (tags/categories)
  - posts
  - postmeta
