ID = $(shell basename $$(pwd))

FILES = BP35A1.py \
        charge.py \
        chargedb.py	\
    	mqtt.py \
        ntptime.py \
        logging.py

APPS =  apps/SMM.py

CFGS =  calendar_2026.json \
        nencho_saiene.json\
        SmartMeter.json \
        tepco_b.json

all: $(CFGS)

# refresh json config in utils
refresh:
	cd ./utils && ./refresh.sh

# push json config from utils into staging
%.json: utils/%.json
	cp $< $@

# push into device from staging
push:
	mpremote cp $(CFGS) :
	mpremote cp $(FILES) :
	mpremote cp $(APPS) :apps

# run against local apps/SMM.py
run:
	mpremote run apps/SMM.py

connect:
	@echo "Use ^C to break from bootup to get into Python prompt, then ^] to exit mpremote"
	mpremote connect /dev/tty.wchusbserial5B1E0460401
