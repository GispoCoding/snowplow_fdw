# snowplow_fdw
PostgreSQL foreign data wrapper for json data from snowplow

Inspired greatly by [geofdw](https://github.com/bosth/geofdw).

# Installation

## Development
1. Install docker and docker-compose.
2. `docker-compose up -d --build`
3. Install snowplow_fdw foreign data wrapper with: `docker-compose exec postgis-db bash /scripts/dev_install.sh`
4. If you make any changes to the code, just repeat the installation
5. Run `docker ps` to find out postgis-db docker name (<postgis-db-name> in next)
7. Run docker cp docker/pg_hba.conf <postgis-db-name>:/etc/postgresql/12/main/
8. Run `docker-compose exec postgis-db bash chown postgres:postgres /etc/postgresql/12/main/pg_hba.conf`
7. Restart with `docker-compose restart postgis-db`


## Production (Tested in Debian buster)

1. Install dependencies
    ```shell script
    # Assuming you are running with root permissions (otherwise add sudo) and have postgresql and postgis installed 
    apt update
    apt install python python3 python3-dev python3-pip pgxnclient
    pip3 install setuptools
    ```
3. Connect to your database and enable Multicorn
    ```sql
    CREATE EXTENSION postgis;
    CREATE EXTENSION multicorn;
    ```
4. Go to the to directory where you cloned the project and install it with:
    ```shell script
    python3 setup.py install
    ```

You have to restart Postgresql in order to find the package (`systemctl postgresql restart` or `service postgresql restart`).

# Usage

### Creating a fdw server
```sql
CREATE SERVER dev_fdw FOREIGN DATA WRAPPER multicorn OPTIONS (wrapper 'snowplowfdw.ConstantForeignDataWrapper');
```
