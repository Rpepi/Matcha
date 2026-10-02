-- KEYS[1] = this bucket's key         (e.g. "rl:login:ip:192.168.1.5")
-- ARGV[1] = burst : bucket size       (how many tokens it can hold)
-- ARGV[2] = rate  : tokens refilled per second

local burst = tonumber(ARGV[1])
local rate  = tonumber(ARGV[2])

-- Ask Redis for the time (not Python) so everyone agrees on the same clock
local t   = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000

-- Re-read the bucket's state: how many tokens are left, and since when
local state  = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(state[1])
local ts     = tonumber(state[2])

if tokens == nil then
    -- First request from this user: the bucket starts full
    tokens = burst
else
    -- Refill: elapsed time x rate, never exceeding the bucket size
    tokens = math.min(burst, tokens + (now - ts) * rate)
end

local allowed = 0
local retry_after = 0

if tokens >= 1 then
    tokens = tokens - 1                        -- consume one token
    allowed = 1
else
    retry_after = math.ceil((1 - tokens) / rate)  -- seconds until the next token
end

-- Save the bucket's new state
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)

-- If the user never comes back, the key expires on its own
redis.call('EXPIRE', KEYS[1], math.ceil(burst / rate) + 1)

return {allowed, math.floor(tokens), retry_after}