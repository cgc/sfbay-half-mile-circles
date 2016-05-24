deploy:
	git fetch
	git checkout gh-pages
	git reset --hard origin/master
	npm run build
	git add -f dist.js
	git commit -am 'deploy'
	git push origin gh-pages -f
