# snowplow_fdw

PostgreSQL Foreign Data Wrapper for JSON data from Snowplow API.

Inspired greatly by [geofdw](https://github.com/bosth/geofdw).

# Installation

## Development

1. Install docker and docker-compose.
2. Run `docker-compose up -d --build` (if you are not running with root permissions add `sudo` in the beginning of each command)
3. Install snowplow_fdw Foreign Data Wrapper with: `docker-compose exec postgis-db bash /scripts/dev_install.sh`
4. Run `docker ps` to find out postgis-db docker name (`<postgis-db-name>` in next)
5. Run `docker cp docker/pg_hba.conf snowplow_fdw_<postgis-db-name>:/etc/postgresql/12/main/`
6. Run `docker-compose exec postgis-db bash`
7. Run `chown postgres:postgres /etc/postgresql/12/main/pg_hba.conf` and `exit`
8. Restart with `docker-compose restart postgis-db`

If you make any changes to the code, just repeat the installation (steps 3-9). 
Stop database with `docker-compose stop` and start it next time with `docker-compose start`.

## Production (tested in Debian buster)

1. Install dependencies:
    ```shell script
    # Assuming that you have PostgreSQL and PostGIS installed 
    apt update
    apt install python python3 python3-dev python3-pip pgxnclient
    pip3 install setuptools
    
    # Install Multicorn for Foreign Data Wrappers
    pgxn install multicorn

    # Install plpygis for Foreign Data Wrapper support for Postgis
    pip3 install -q plpygis
    pip3 install -q requests
    ```

2. Connect to your database and enable Multicorn and pg_cron extension (for scheduling tasks):
    ```sql
    CREATE EXTENSION postgis;
    CREATE EXTENSION multicorn;
    CREATE EXTENSION IF NOT EXISTS pg_cron;
    GRANT USAGE ON SCHEMA cron TO <your username>;
    ```

3. Go to the to directory where you cloned the project and install it with:
    ```shell script
    python3 setup.py install
    ```

You have to restart PostgreSQL in order to find the package (`systemctl postgresql restart` or `service postgresql restart`).

# Usage

### Creating a fdw server

```sql
CREATE SERVER dev_fdw FOREIGN DATA WRAPPER multicorn OPTIONS (wrapper 'snowplowfdw.SnowplowForeignDataWrapper');
```

### Creating a metatable containing unit information

Create a foreign table:
```sql
CREATE FOREIGN TABLE units_temp(
    id integer,
    name varchar
    ) server dev_fdw options(
    url '<url to the unit list>'
);
```

Create a table for storing the unit information fetched from the Snowplow API:
```sql
CREATE TABLE units(
    id integer,
    name varchar
);
```

Insert data from the foreign table to the `units` table:
```sql
INSERT INTO units(
    id, name)
SELECT id, name FROM units_temp;
```

### Creating a function for updating history information of the active units

Create an `idupdate` function (Language: plpgsql, Return type: void) for determining which units have
been active after the previous time we gathered units' location history data.
Create the function under cron schema with the following code:
```sql
BEGIN
	DROP SERVER IF EXISTS dev_fdw CASCADE;
	DROP FOREIGN TABLE IF EXISTS idtemp;

	CREATE SERVER dev_fdw FOREIGN DATA WRAPPER multicorn OPTIONS ( wrapper 'snowplowfdw.SnowplowForeignDataWrapper' );
	
	CREATE FOREIGN TABLE idtemp(
		id varchar,
		machine_type varchar,
		last_timestamp timestamptz,
		last_coords varchar,
		last_events varchar
		) server dev_fdw options(
		url '<url to the page containing latest information about units' whereabouts>');

	UPDATE idtable
	SET last_timestamp = idtemp.last_timestamp,
	last_coords = ('POINT' || idtemp.last_coords)::geography,
	last_events = CAST(TRIM(CAST(idtemp.last_events as text),'['']') as text),
	machine_type = idtemp.machine_type
	FROM idtemp
	WHERE idtable.id = CAST(idtemp.id as integer);

	with result as(
		SELECT *
		FROM idtemp l
		WHERE NOT EXISTS (
			SELECT
			FROM idtable
			WHERE CAST(id as text) = l.id)
	)
		
	INSERT INTO idtable(
		id, machine_type, last_timestamp, last_coords, last_events)
	SELECT CAST(id as integer), machine_type, last_timestamp, ('POINT' || "last_coords")::geography, CAST(TRIM(CAST("last_events" as text),'['']') as text)
	FROM result;

END;
```

Create a table for storing latest information about units:
```sql
CREATE TABLE idtable(
   id integer,
   machine_type varchar,
   last_timestamp timestamp,
   last_coords geography,
   last_events varchar
);
```

Create a `dataupdate` function (Language: plpgsql, Return type: void) for taking care of gathering
active units' location history data.  Create the function under cron schema with the following code:
```sql
declare
	temprow record;
	aa varchar(250);
	bb varchar(250);
	cc varchar(250) := '<beginning part of the url (before unit ID)>';
	dd varchar(250) := '<rest of the url (after unit ID)>';

BEGIN
	
	FOR temprow IN
		SELECT CAST(id as text) as idtxt FROM idtable WHERE last_timestamp >= current_timestamp at time zone '<any time zone>' - interval '<any time interval 1>'
	LOOP
		DROP SERVER IF EXISTS dev_fdw CASCADE;
		DROP FOREIGN TABLE IF EXISTS tabletemp;

		CREATE SERVER dev_fdw FOREIGN DATA WRAPPER multicorn OPTIONS ( wrapper 'snowplowfdw.SnowplowForeignDataWrapper' );
		
		aa := temprow.idtxt;
		bb := cc || aa || dd;
		
		EXECUTE format('CREATE FOREIGN TABLE tabletemp(
			id varchar,
			timestamp timestamptz,
			coords varchar,
			events varchar
			) server dev_fdw options(
			url %L
					   )', bb
			);
		
		INSERT INTO datatable(
			id, timestamp, coords, events)
		SELECT CAST(id as integer), timestamp, ('POINT' || "coords")::geography, CAST(TRIM(CAST("events" as text),'['']') as text)
		FROM tabletemp
		WHERE extract(doy from timestamp)=extract(doy from current_timestamp at time zone '<any time zone>') and extract(hour from timestamp) = extract(hour from current_timestamp at time zone '<any time zone>' - interval '<any time interval 2>');
	
	END LOOP;

END;
```

Create a table for storing history data of the units:
```sql
CREATE TABLE datatable(
    id integer,
    timestamp timestamp,
    coords geography,
    events varchar
);
```

In case you wish to perform the scheduled history data gathering task e.g. once in every hour,
execute the following commands:
```sql
SELECT cron.schedule('1 */1 * * *',  $$select cron.idupdate()$$);
SELECT cron.schedule('5 */1 * * *',  $$select cron.dataupdate()$$);
```

The commands state that the `idupdate` function gets ran one minute past every hour and the
`dataupdate` function gets ran five minutes past every hour.

Note that if you schedule the tasks to be run once in every hour, some suitable choices for
`<any time interval 1>` and `<any time interval 2>` are '1 hour 15 minutes' and '1 hour'. In that
case one suitable choice for a number of rows we wish to fetch (needed when forming
`<rest of the url (after unit ID)>`) is 1000.

Once you want to terminate the execution of the scheduled tasks, run:
```sql
SELECT cron.unschedule(<job id>);
```

To get more knowledge about the scheduled tasks, you can run queries like
```sql
SELECT *
FROM cron.job;
```
or
```sql
SELECT *
FROM cron.job_run_details
WHERE jobid=<job id>;
```
