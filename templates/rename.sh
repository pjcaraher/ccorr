# sed -i -- 's/ccorr-staging.ke6wrptupr.us-west-2.elasticbeanstalk.com:8888/0.0.0.0:8888/g' *.html
sed -i -- 's/0.0.0.0:8888/localhost:8888/g' *.html
rm -rf *.html--
