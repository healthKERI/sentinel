sequenceDiagram
actor User
participant Locksmith
participant healthKERI
participant Sentinel

    User ->> Locksmith: Add Machine request
    Locksmith ->> healthKERI: add machine
    healthKERI -->> Locksmith: Return auth-key
    Locksmith -->> User: Return auth-key
    User ->> Sentinel: sentinel up (auth-key)
    Sentinel ->> healthKERI: register (auth-key)
    healthKERI ->> healthKERI: spin up witnesses
    healthKERI -->> Sentinel: Return OOBIs
    Sentinel ->> Sentinel: resolve witness OOBIs
    Sentinel ->> healthKERI: update (rotation event)
    healthKERI -->> Sentinel: success
    Sentinel -->> User: success
    healthKERI -->> Locksmith: Machine state changed notification
    User ->> Locksmith: rotate in witnesses
    Locksmith ->> healthKERI: rotate in witnesses
    healthKERI -->> Locksmith: success
    Locksmith -->> User: success
    User ->> Sentinel: Start up
    loop Poll until approval complete
        Sentinel ->> healthKERI: check approval status
        healthKERI -->> Sentinel: approval (pending or complete)
    end
    Sentinel -->> User: Startup Complete