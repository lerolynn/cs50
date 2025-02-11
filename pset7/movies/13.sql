SELECT DISTINCT(people.name) FROM people
JOIN stars ON stars.person_id = people.id
JOIN movies ON movies.id = stars.movie_id
WHERE movies.id

IN (SELECT movies.id FROM movies
JOIN stars ON movies.id = stars.movie_id
JOIN people ON stars.person_id = people.id
WHERE people.name = "Kevin Bacon" AND people.birth = 1958)

AND people.name
NOT IN (SELECT name FROM people WHERE name = "Kevin Bacon" AND birth = 1958);