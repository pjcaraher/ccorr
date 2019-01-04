# sed -i -- 's/ccorr-staging.ke6wrptupr.us-west-2.elasticbeanstalk.com:8888/0.0.0.0:8888/g' *.html
sed -i -- 's/localhost:8888/{{ config.BASEURL }}/g' *.html
rm -rf *.html--
