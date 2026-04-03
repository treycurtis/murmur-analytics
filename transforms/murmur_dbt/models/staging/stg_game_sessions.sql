with source as (

    select * from {{ source('murmur', 'game_sessions') }}

),

renamed as (

    select
        id                                  as session_id,
        channel_id,
        channel_type,
        campaign,
        label,
        is_active,
        owner_id,
        outcome,
        campaign_summary::integer           as campaign_summary,
        invite_token_hash,
        created_at::timestamp_ntz           as created_at,
        updated_at::timestamp_ntz           as updated_at,
        ended_at::timestamp_ntz             as ended_at

    from source

)

select * from renamed