#!/bin/sh -x



if [ ! -f $HVR_CONFIG/etc/hvrhubserver.conf ]; then

    echo "Waiting for the database"

    while ! nc -z ${HVR_DB_HOST} ${HVR_DB_PORT}; do   
        sleep 1
    done

    # define the connection to the hub
    hvrhubserverconfig \
        HTTP_Port=${HVR_HTTP_PORT} \
        Repository_Class=${HVR_REPO_CLASS} \
        Database_Host=${HVR_DB_HOST} \
        Database_Port=${HVR_DB_PORT} \
        Database_Name=${HVR_DB_NAME} \
        Database_User=${HVR_DB_USERNAME} \
        Database_Password="${HVR_DB_PASSWORD}" \
        $HVR_SERVER_CONFIG_OPTS

    # configure the repository
    hvrreposconfig -c

    # apply the license file
    hvrlicense ${HVR_HOME}/license/hvr.lic

    # Create initial admin user (local auth) if specified
    if [ -n "$HVR_ADMIN_PASSWORD" ]; then
        echo "$HVR_ADMIN_PASSWORD" > /tmp/.adminpass
        echo "$HVR_ADMIN_PASSWORD" > /tmp/.adminpass
        
        cat /tmp/.adminpass | hvruserconfig -c admin
        hvrreposconfig -A user:admin=SysAdmin
        
        rm -f /tmp/.adminpass
    fi

    hvrwalletconfig -c Type=DISABLED

    hvrhubconfig -c antares Description="${HVR_HUB_NAME}"

    # If there is an export file to import initially, then let's do it
    if [ -n "$HVR_EXPORT_FILE" ]; then
        curl "$HVR_EXPORT_FILE" > /tmp/export.json
        hvrdefinitionimport -a REPLACE antares /tmp/export.json
        rm -f /tmp/export.json
    fi
fi

# in case the PVC is the same but we were restarted on a different node
rm -f $HVR_CONFIG/run/*.pid

# Start the hub and the scheduler
hvrhubserver -i